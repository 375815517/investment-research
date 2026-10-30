import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { splitDocument, renderMarkdown } from './markdown.js';

export const digest = text => createHash('sha256').update(text).digest('hex');
const slugPattern = /^[a-z][a-z0-9-]{0,63}$/;
const sharedNames = ['README.md', 'profile.md', 'methods.md', 'sources.md', 'questions.md', 'learnings.md'];
export const fail = (message, status = 400) => Object.assign(new Error(message), { status });
const label = (value, max = 160) => {
  if (typeof value !== 'string' || !value.trim() || value.length > max || /[\x00-\x1f]/.test(value)) throw fail('请填写有效文本，且不要包含换行。');
  return value.trim();
};
export const frontmatter = (meta, body) => '---\n' + Object.entries(meta).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join('\n') + '\n---\n\n' + body;
// Preserve previously saved document links while all new writes use project paths.
function canonicalPath(relative) {
  const common = ['rules.md','methodology.md','data-contract.md','lessons.md'];
  if (common.includes(relative)) return 'framework/' + relative;
  if (relative.startsWith('templates/')) return 'framework/' + relative;
  if (/^playbooks\/[a-z-]+\.md$/.test(relative)) return 'industries/' + relative.slice(10,-3) + '/methodology.md';
  return relative.replace(/^(companies\/[^/]+)\/shared\//, '$1/knowledge/');
}
export function createLibrary(root) {
  root = path.resolve(root);
  // All document IO passes through this boundary; symbolic links never extend the library.
  function resolve(relative, allowMissing = false) {
    if (typeof relative !== 'string' || !relative || relative.length > 500 || relative.includes('\\') || relative.includes('\0') || path.isAbsolute(relative)) throw fail('资料路径无效。');
    relative = canonicalPath(relative);
    const parts = relative.split('/');
    if (parts.some(p => !p || p.startsWith('.') || p === '..')) throw fail('资料路径越界。', 403);
    let current = path.parse(root).root;
    for (const part of path.relative(current, root).split(path.sep).concat(parts)) {
      current = path.join(current, part);
      if (fs.existsSync(current)) {
        if (fs.lstatSync(current).isSymbolicLink()) throw fail('资料目录不允许符号链接。', 403);
      } else if (!allowMissing) throw fail('未找到资料。', 404);
    }
    return current;
  }
  function read(relative) {
    if (!/\.(md|csv|json)$/.test(relative)) throw fail('仅支持 Markdown、CSV 与 JSON 资料。');
    const file = resolve(relative);
    if (fs.statSync(file).size > 2 * 1024 * 1024) throw fail('文档超过 2 MB，请拆分。', 413);
    const content = fs.readFileSync(file, 'utf8');
    return { path: relative, content, digest: digest(content), ...splitDocument(content) };
  }
  function files(directory = '') {
    const result = [];
    function walk(rel) {
      const dir = rel ? resolve(rel) : root;
      if (fs.lstatSync(dir).isSymbolicLink()) throw fail('资料根不能是符号链接。', 403);
      for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
        if (item.name.startsWith('.') || item.isSymbolicLink() || ['web','apps','tools','docs','node_modules','raw'].includes(item.name)) continue;
        const child = rel ? `${rel}/${item.name}` : item.name;
        if (item.isDirectory()) walk(child);
        else if (/\.(md|csv)$/.test(item.name)) result.push(child);
      }
    }
    walk(directory); return result;
  }
  function editable(relative) {
    relative = canonicalPath(relative);
    if (['framework/rules.md', 'framework/methodology.md', 'framework/lessons.md'].includes(relative)) return true;
    if (/^companies\/[a-z][a-z0-9-]*\/knowledge\/(profile|methods|sources|questions|learnings)\.md$/.test(relative)) return true;
    if (/^companies\/[a-z][a-z0-9-]*\/analyses\/[^/]+\/retrospective\.md$/.test(relative)) return true;
    const match = /^(companies\/[a-z][a-z0-9-]*\/analyses\/[^/]+)\/(report\.md|facts\.csv|sources\.md|assumptions\.md|retrospective\.md)$/.exec(relative);
    return !!match && read(`${match[1]}/report.md`).meta.status === 'draft';
  }
  function atomicWrite(relative, content, expected) {
    const file = resolve(relative);
    if (digest(fs.readFileSync(file, 'utf8')) !== expected) throw fail('文档已被其他窗口或编辑器更新。请重新打开后再保存；你的输入仍保留。', 409);
    const tmp = `${file}.${randomUUID()}.tmp`;
    try { fs.writeFileSync(tmp, content, { flag: 'wx', mode: 0o600 }); fs.renameSync(tmp, file); }
    finally { if (fs.existsSync(tmp)) fs.unlinkSync(tmp); }
    return read(relative);
  }
  function save(relative, content, expected) {
    if (!editable(relative)) throw fail('历史分析正文与系统入口只读，请创建新分析或追加验证。', 403);
    if (typeof content !== 'string' || Buffer.byteLength(content) > 1024 * 1024) throw fail('文档内容过大。', 413);
    if (relative.endsWith('/report.md') && splitDocument(content).meta.status !== 'draft') throw fail('草稿状态不能通过正文编辑修改。');
    return atomicWrite(relative, content, expected);
  }
  function createFolder(relative, documents) {
    const target = resolve(relative, true); if (fs.existsSync(target)) throw fail('同名目录已存在，请换一个标识。', 409);
    const parent = path.dirname(target); fs.mkdirSync(parent, { recursive: true });
    const staging = path.join(parent, `.new-${randomUUID()}`); fs.mkdirSync(staging, { mode: 0o700 });
    try {
      for (const [name, content] of Object.entries(documents)) { const p = path.join(staging, name); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, content, { flag: 'wx', mode: 0o600 }); }
      fs.renameSync(staging, target);
    } finally { if (fs.existsSync(staging)) fs.rmSync(staging, { recursive: true }); }
    return relative;
  }
  function createCompany(input) {
    const slug = label(input.slug, 64); if (!slugPattern.test(slug)) throw fail('公司标识使用小写字母、数字和短横线，以字母开头。');
    const name = label(input.name); const ticker = label(input.ticker || '未填写', 40); const sector = label(input.sector || '待分类', 80);
    const titles = { 'profile.md': '公司概况', 'methods.md': '公司专用方法', 'sources.md': '常用数据源', 'questions.md': '待验证事项', 'learnings.md': '公司复盘' };
    const documents = { 'knowledge/README.md': frontmatter({ name, ticker, sector, summary: '从一个可验证的问题开始研究。' }, `# ${name}\n\n公共资料持续维护；每次分析保存在 analyses 独立目录。\n`) };
    for (const [file, title] of Object.entries(titles)) documents[`knowledge/${file}`] = `# ${title}\n\n${file === 'questions.md' ? '- [ ] 补齐最新财报与业务结构；记录来源、口径和判断被推翻的条件。\n' : '待补充。请按全局规则记录来源、时点和推断边界。\n'}`;
    createFolder(`companies/${slug}`, documents); return slug;
  }
  function createAnalysis(input) {
    const company = label(input.company, 64); if (!slugPattern.test(company)) throw fail('公司标识无效。');
    const profile = read(`companies/${company}/knowledge/README.md`).meta;
    const title = label(input.title); const date = input.date || new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date());
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw fail('日期应为有效的 YYYY-MM-DD。');
    const run = `${date}-${randomUUID().slice(0, 8)}`; const relative = `companies/${company}/analyses/${run}`;
    const contextFiles = ['framework/rules.md', 'framework/methodology.md', ...sharedNames.map(x => `companies/${company}/knowledge/${x}`), ...files().filter(p=>p==='framework/data-contract.md'||p.startsWith('industries/'))];
    const context = '# 创建时的公共上下文快照\n\n后续公共资料更新不会改写本快照。来源文件及SHA-256如下。\n\n' + contextFiles.map(p => { const d = read(p); return `## ${p}\n\n摘要：${d.digest}\n\n${d.content}\n`; }).join('\n');
    const template = read('framework/templates/analysis.md').body;
    createFolder(relative, {
      'report.md': frontmatter({ title, company, asOf: date, status: 'draft', summary: '研究进行中，尚未形成结论。' }, template.replaceAll('{{company}}', profile.name).replaceAll('{{title}}', title)),
      'context.md': context, 'facts.csv': 'fact_id,metric,period,value,unit,source_id,locator,kind\n',
      'claims.csv': 'claim_id,claim,fact_ids,counterevidence,invalidation,status\n',
      'runs/base/parameters.json': JSON.stringify({status:'not_computed',events:[],scenarios:[]},null,2),
      'runs/base/results.csv': 'metric,value,unit,formula,inputs\n',
      'runs/base/event-returns.csv': 'event_id,event_date,title,aligned_date,return_1_session_pct\n',
      'runs/base/manifest.json': JSON.stringify({status:'not_computed'},null,2),
      'sources.md': '# 本次来源\n\n记录原始URL、发布/访问时间、页码、适用口径和复核状态。\n',
      'assumptions.md': '# 假设与情景\n\n每项假设注明依据、反证和敏感性；不将情景写成公司指引。\n',
      'verification.md': '# 验证记录\n\n本文件按时间追加，不覆盖旧观察。\n',
      'retrospective.md': '# 复盘\n\n## 当时判断\n\n## 后续实际结果\n\n## 偏差原因\n\n## 可复用改进\n'
    }); return `${relative}/report.md`;
  }
  function appendVerification(input) {
    const { relative, expected, question, observation, source, outcome } = input;
    if (!/^companies\/[a-z][a-z0-9-]*\/analyses\/[^/]+\/verification\.md$/.test(relative)) throw fail('请在具体分析中追加验证。');
    label(question, 500); label(observation, 3000);
    if (!['支持', '反证', '未解决'].includes(outcome)) throw fail('请选择验证结果。');
    let url; try { url = new URL(source); } catch { throw fail('请填写有效来源链接。'); } if (!['http:', 'https:'].includes(url.protocol)) throw fail('来源使用 http 或 https 链接。');
    const previous = read(relative);
    const block = `\n## ${new Date().toISOString()}｜${outcome}\n\n问题：${question}\n\n观察：${observation}\n\n来源：${url.href}\n\n本记录仅表达此次观察，不自动改变公司结论。\n`;
    return atomicWrite(relative, previous.content + block, expected);
  }
  function catalog() {
    const documents = files().map(p => { const d = read(p); return { path: p, title: d.meta.title || /^#\s+(.*)$/m.exec(d.body)?.[1] || path.basename(p), ...d.meta, excerpt: d.body.replace(/[#*|`]/g, '').slice(0, 180), editable: editable(p) }; });
    const companies = documents.filter(d => /^companies\/[^/]+\/knowledge\/README.md$/.test(d.path)).map(d => ({ ...d, slug: d.path.split('/')[1], analyses: documents.filter(a => a.path.startsWith(`companies/${d.path.split('/')[1]}/analyses/`) && a.path.endsWith('/report.md')).sort((a, b) => b.path.localeCompare(a.path)) }));
    const questions = documents.filter(d => d.path.endsWith('/knowledge/questions.md')).flatMap(d => read(d.path).body.split('\n').filter(x => /^- \[ \]/.test(x)).map(x => ({ company: d.path.split('/')[1], path: d.path, text: x.slice(6).trim() })));
    return { companies, documents, questions, counts: { companies: companies.length, analyses: companies.reduce((n, c) => n + c.analyses.length, 0), questions: questions.length, documents: documents.length } };
  }
  function document(relative) { const d = read(relative); return { ...d, html: /\.(csv|json)$/.test(relative) ? '' : renderMarkdown(d.content, relative), editable: editable(relative) }; }
  function attachment(relative) {
    if(!/^companies\/[a-z][a-z0-9-]*\/sources\/[^/]+\.pdf$/.test(relative))throw fail('仅可读取已归档公司PDF。',403);
    const file=resolve(relative); if(fs.statSync(file).size>50*1024*1024)throw fail('原件过大。',413);return fs.readFileSync(file);
  }
  function market() {
    const data=JSON.parse(read('companies/xiaomi/data/market/dashboard.json').content);
    data.status=JSON.parse(read('companies/xiaomi/data/market/status.json').content);
    data.projectionStale=data.price_digest!==read('companies/xiaomi/data/market/prices.csv').digest;
    return data;
  }
  function search(query) {
    if (typeof query !== 'string' || query.length > 200) throw fail('检索词过长。');
    query = query.trim().toLocaleLowerCase(); if (!query) return [];
    return files().flatMap(p => { const d = read(p); const i = d.content.toLocaleLowerCase().indexOf(query); return i < 0 ? [] : [{ path: p, title: d.meta.title || /^#\s+(.*)$/m.exec(d.body)?.[1] || p, excerpt: d.content.slice(Math.max(0, i - 40), i + 140) }]; }).slice(0, 100);
  }
  return { root, read, files, document, catalog, search, save, createCompany, createAnalysis, appendVerification, attachment, market };
}
