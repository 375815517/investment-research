import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pipeline as p

NOW=datetime(2026,10,21,18,tzinfo=ZoneInfo('Asia/Hong_Kong'))

def payload(candles):
    return json.dumps({'code':0,'data':{'hk01810':{'day':candles}}}).encode()

class PipelineTests(unittest.TestCase):
    def test_refresh_repeat_failure_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            data=payload([['2026-10-16','10','11','12','9','100'],['2026-10-20','11','12','13','10','200']])
            p.refresh(root,data,NOW)
            f=root/'companies/xiaomi/data/market/prices.csv'
            first=f.read_bytes()
            p.refresh(root,data,NOW)
            self.assertEqual(first,f.read_bytes())
            self.assertEqual(len(p.rows(f)),2)
            with self.assertRaises(ValueError):
                p.refresh(root,payload([['2026-10-21','11','90','13','10','200']]),NOW)
            self.assertEqual(first,f.read_bytes())
            state=json.loads((f.parent/'status.json').read_text())
            self.assertEqual(state['state'],'failed')
            self.assertEqual(state['as_of'],'2026-10-20')
            self.assertTrue(state['last_success'])
            with patch.object(p,'urlopen',side_effect=TimeoutError('offline')):
                with self.assertRaises(TimeoutError):p.refresh(root,now=NOW)
            self.assertEqual(first,f.read_bytes())
            p.refresh(root,payload([['2026-10-21','12','13','14','11','300']]),NOW)
            self.assertEqual(len(p.rows(f)),3)

    def test_incomplete_day_and_duplicates(self):
        data=payload([['2026-10-20','10','11','12','9','100'],['2026-10-21','11','12','13','10','200']])
        self.assertEqual(len(p.normalize(data,NOW.replace(hour=14))),1)
        self.assertEqual(len(p.normalize(data,NOW)),2)
        with self.assertRaises(ValueError):
            p.normalize(payload([['2026-10-20','10','11','12','9','100'],['2026-10-20','10','10','12','9','100']]),NOW)

    def test_event_next_session_and_missing_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'prices.csv'
            p.atomic(f,p.csv_text(p.normalize(payload([['2026-10-16','10','10','12','9','100'],['2026-10-20','10','11','12','9','100'],['2026-10-21','11','12','13','10','100']]),NOW),p.FIELDS))
            conn=p.db();p.price_view(conn,f)
            result=p.event_returns(conn,[{'event_id':'E1','event_date':'2026-10-17','title':'周末事件'},{'event_id':'E2','event_date':'2026-10-22','title':'未来'}])
            self.assertEqual(result[0]['aligned_date'],'2026-10-20')
            self.assertEqual(result[0]['return_1_session_pct'],10)
            self.assertEqual(result[0]['return_5_sessions_pct'],'')
            self.assertEqual(result[1]['aligned_date'],'')
            conn.close()

    def test_csv_quoted_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'facts.csv';p.atomic(f,p.csv_text([{'id':'A','note':'数字, 引号"与\n换行'}],['id','note']))
            self.assertEqual(p.rows(f)[0]['note'],'数字, 引号"与\n换行')

if __name__=='__main__':unittest.main()
