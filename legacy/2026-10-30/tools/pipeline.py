"""File-authoritative market refresh and reproducible Xiaomi research calculations."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk01810,day,,,320,'
FIELDS = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'currency', 'adjustment', 'provider']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def dump(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def csv_text(rows, fields):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def rows(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def normalize(payload, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Hong_Kong'))
    data = json.loads(payload)
    if data.get('code') != 0:
        raise ValueError('行情提供方返回错误，旧数据保留')
    candles = data['data']['hk01810']['day']  # Explicit unadjusted series, never silently use qfqday.
    result = {}
    for item in candles:
        day, opening, close, high, low, volume = item[:6]
        date = datetime.strptime(day, '%Y-%m-%d').date()
        if date > now.date() or (date == now.date() and now.hour < 17):
            continue  # Exclude incomplete HK session, allow after-close ingestion.
        o, c, h, l, v = map(float, (opening, close, high, low, volume))
        if not all(map(math.isfinite, (o, c, h, l, v))) or min(o, c, h, l) <= 0 or v < 0 or v != int(v) or not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError(f'行情质量校验失败：{day}')
        row = dict(zip(FIELDS, ['1810.HK', day, o, h, l, c, int(v), 'HKD', 'none', 'Tencent Finance']))
        if day in result and result[day] != row:
            raise ValueError(f'同批次行情日期冲突：{day}')
        result[day] = row
    if not result:
        raise ValueError('没有已收盘的有效日线')
    return [result[d] for d in sorted(result)]


def db():
    import duckdb
    return duckdb.connect(':memory:')


def price_view(conn, path):
    conn.read_csv(str(path), header=True, columns={
        'symbol': 'VARCHAR', 'date': 'DATE', 'open': 'DOUBLE', 'high': 'DOUBLE',
        'low': 'DOUBLE', 'close': 'DOUBLE', 'volume': 'BIGINT', 'currency': 'VARCHAR',
        'adjustment': 'VARCHAR', 'provider': 'VARCHAR'}).create_view('prices')


def event_returns(conn, events):
    output = []
    for event in events:
        # Date-only disclosures use the next session, avoiding assumptions about publication time.
        candle = conn.execute('SELECT date, close FROM prices WHERE date > ? ORDER BY date LIMIT 1', [event['event_date']]).fetchone()
        before = conn.execute('SELECT date, close FROM prices WHERE date <= ? ORDER BY date DESC LIMIT 1', [event['event_date']]).fetchone()
        value = dict(event, aligned_date='', baseline_date='', return_1_session_pct='', return_5_sessions_pct='', alignment='next-session-date-only')
        if candle and before:
            value.update(aligned_date=str(candle[0]), baseline_date=str(before[0]), return_1_session_pct=round((candle[1] / before[1] - 1) * 100, 4))
            fifth = conn.execute('SELECT close FROM prices WHERE date >= ? ORDER BY date LIMIT 1 OFFSET 4', [candle[0]]).fetchone()
            if fifth:
                value['return_5_sessions_pct'] = round((fifth[0] / before[1] - 1) * 100, 4)
        output.append(value)
    return output


def dashboard(root):
    folder = root / 'companies/xiaomi/data/market'
    conn = db()
    price_view(conn, folder / 'prices.csv')
    points = [dict(date=str(d), close=c, volume=v) for d, c, v in conn.execute('SELECT date, close, volume FROM prices ORDER BY date').fetchall()]
    events = rows(root / 'companies/xiaomi/data/events.csv') if (root / 'companies/xiaomi/data/events.csv').exists() else []
    status = json.loads((folder / 'status.json').read_text()) if (folder / 'status.json').exists() else {}
    result = {'symbol': '1810.HK', 'currency': 'HKD', 'adjustment': 'none', 'price_digest': sha(folder / 'prices.csv'), 'status': status, 'points': points, 'events': event_returns(conn, events)}
    dump(folder / 'dashboard.json', result)
    conn.close()
    return result


def refresh(root, payload=None, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Hong_Kong'))
    folder = root / 'companies/xiaomi/data/market'
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / '.refresh.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    previous = json.loads((folder / 'status.json').read_text()) if (folder / 'status.json').exists() else {}
    try:
        raw = payload if payload is not None else urlopen(URL, timeout=25).read()
        incoming = normalize(raw, now)
        old = rows(folder / 'prices.csv') if (folder / 'prices.csv').exists() else []
        merged = {r['date']: r for r in old}
        merged.update({r['date']: r for r in incoming})
        material = [merged[d] for d in sorted(merged)]
        # Archive each distinct response; never overwrite a different snapshot from the same day.
        archive = folder / 'raw' / (now.date().isoformat() + '.json')
        content = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        if archive.exists() and archive.read_text() != content:
            archive = archive.with_name(archive.stem + '-' + hashlib.sha256(content.encode()).hexdigest()[:12] + '.json')
        atomic(archive, content)
        atomic(folder / 'prices.csv', csv_text(material, FIELDS))
        state = {'state': 'ok', 'last_attempt': now.isoformat(), 'last_success': now.isoformat(), 'as_of': material[-1]['date'], 'rows': len(material), 'source_url': URL, 'raw_path': str(archive.relative_to(root)), 'raw_sha256': sha(archive), 'note': '不复权已收盘日线；修订覆盖当前序列，历史原始响应和研究快照保留'}
        dump(folder / 'status.json', state)
        try:
            dashboard(root)
        except Exception as error:
            state.update(state='projection_failed', error=str(error))
            dump(folder / 'status.json', state)
            raise
        return state
    except Exception as error:
        # Durable CSV is untouched for acquisition/validation failures; never write an empty replacement.
        state = json.loads((folder / 'status.json').read_text()) if (folder / 'status.json').exists() else previous
        state.update(state='failed', last_attempt=now.isoformat(), error=str(error))
        dump(folder / 'status.json', state)
        raise
    finally:
        lock.unlink()


def calculate(root, analysis):
    folder = root / analysis
    run = folder / 'runs/base'
    params = json.loads((run / 'parameters.json').read_text())
    fact_rows = rows(folder / 'facts.csv')
    facts = {r['fact_id']: float(r['value']) for r in fact_rows if r['kind'] in ('disclosed', 'company_guidance')}
    if len({r['fact_id'] for r in fact_rows}) != len(fact_rows):
        raise ValueError('重复事实ID')
    for claim in rows(folder / 'claims.csv'):
        for identifier in claim['fact_ids'].split(';'):
            if identifier and identifier not in {r['fact_id'] for r in fact_rows}:
                raise ValueError('判断引用缺失事实：' + identifier)
    conn = db()
    price_view(conn, folder / 'inputs/prices.csv')
    asof = params['price_as_of']
    price = conn.execute('SELECT date,close FROM prices WHERE date <= ? ORDER BY date DESC LIMIT 1', [asof]).fetchone()
    if not price:
        raise ValueError('截至日没有股价')
    result = []
    def add(metric, value, unit, formula, inputs):
        if not math.isfinite(value):
            raise ValueError('非有限结果')
        result.append(dict(metric=metric, value=round(value, 6), unit=unit, formula=formula, inputs=inputs))
    for name, new, old in [('revenue_yoy','F01','F02'), ('adjusted_profit_yoy','F03','F04'), ('operating_cash_yoy','F05','F06'), ('overseas_yoy','F07','F08')]:
        add(name, (facts[new]/facts[old]-1)*100, '%', '(current/prior-1)*100', new+';'+old)
    add('cash_after_selected_asset_purchases',facts['F05']-facts['F09'],'CNY million','CFO-selected asset purchases','F05;F09')
    add('ev_2025_target_excess',facts['F10']-facts['F11'],'vehicles','actual-threshold','F10;F11')
    add('ev_2025_target_excess_pct',(facts['F10']/facts['F11']-1)*100,'%','(actual/threshold-1)*100','F10;F11')
    add('ev_2026_h1_progress',facts['F12']/facts['F13']*100,'%','H1 deliveries/full-year target*100','F12;F13')
    add('snapshot_close',price[1],'HKD','latest close on or before price_as_of','inputs/prices.csv')
    for scenario in params['scenarios']:
        if scenario['shares_million'] <= 0 or scenario['cny_per_hkd'] <= 0:
            raise ValueError('无效股数或汇率假设')
        profit = scenario['revenue_million']*scenario['net_margin']
        target = profit/scenario['shares_million']*scenario['pe']/scenario['cny_per_hkd']
        add(scenario['id']+'_profit',profit,'CNY million','revenue*net_margin','parameters.json')
        add(scenario['id']+'_value',target,'HKD/share','profit/shares*PE/FX','parameters.json')
        add(scenario['id']+'_price_gap',(target/price[1]-1)*100,'%','(scenario value/snapshot close-1)*100','parameters.json;inputs/prices.csv')
    atomic(run / 'results.csv',csv_text(result,['metric','value','unit','formula','inputs']))
    events=event_returns(conn,params['events'])
    if events:
        atomic(run / 'event-returns.csv',csv_text(events,list(events[0])))
    inputs=['facts.csv','claims.csv','inputs/prices.csv','runs/base/parameters.json']
    manifest={'analysis':analysis,'price_as_of':asof,'price_session':str(price[0]),'engine':'DuckDB '+conn.execute('SELECT version()').fetchone()[0], 'formula_sha256':sha(Path(__file__)), 'inputs':{f:sha(folder/f) for f in inputs},'outputs':{f:sha(run/f) for f in ['results.csv','event-returns.csv']},'limits':['行情不复权，收益为价格变化，不含分红/汇率/交易成本','情景为研究者假设，不是公司指引或概率预测','事件采用披露日后首个交易日，不识别因果效应']}
    dump(run / 'manifest.json',manifest)
    conn.close()
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['refresh','dashboard','calculate'])
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input',type=Path,help='显式原始响应，用于离线重放')
    parser.add_argument('--analysis',default='companies/xiaomi/analyses/2026-10-21-growth-evidence')
    args=parser.parse_args()
    if args.command=='refresh':
        output=refresh(args.root,args.input.read_bytes() if args.input else None)
    elif args.command=='dashboard':
        output=dashboard(args.root)
    else:
        output=calculate(args.root,args.analysis)
    print(json.dumps(output,ensure_ascii=False,indent=2))
