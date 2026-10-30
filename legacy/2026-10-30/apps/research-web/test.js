import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createLibrary,frontmatter} from './lib/store.js';
import {renderMarkdown} from './lib/markdown.js';
import {createServer} from './server.js';
test('内部证据链接可导航且不能逃离资料根',()=>{const h=renderMarkdown('[事实](facts.csv) [参数](runs/base/parameters.json) [PDF](../../sources/2026-h1.pdf) [越界](../../../../../../etc/x.pdf)','companies/xiaomi/analyses/trial/report.md');assert.match(h,/#doc\/companies%2Fxiaomi%2Fanalyses%2Ftrial%2Ffacts.csv/);assert.match(h,/\/pdf\?path=/);assert.ok(!h.includes('etc%2Fx'));});
test('行情视图读取真实更新状态并识别过期投影',t=>{const root=fixture(t),lib=createLibrary(root),dir=path.join(root,'companies/xiaomi/data/market');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'prices.csv'),'date,close\n2026-10-20,27.06\n');fs.writeFileSync(path.join(dir,'dashboard.json'),JSON.stringify({points:[],price_digest:'old',status:{state:'ok'}}));fs.writeFileSync(path.join(dir,'status.json'),JSON.stringify({state:'failed',error:'网络失败'}));assert.equal(lib.market().status.state,'failed');assert.equal(lib.market().projectionStale,true);fs.mkdirSync(path.join(root,'web'));fs.writeFileSync(path.join(root,'web/README.md'),'内部源码');assert.ok(!lib.files().includes('web/README.md'));assert.throws(()=>lib.attachment('../private.pdf'));});
function fixture(t){const r=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'investment-test-')));t.after(()=>fs.rmSync(r,{recursive:true,force:true}));fs.mkdirSync(path.join(r,'framework/templates'),{recursive:true});for(const f of ['README.md','rules.md','methodology.md','lessons.md'])fs.writeFileSync(path.join(r,f==='README.md'?f:'framework/'+f),'# '+f+'\n\n原始内容');fs.writeFileSync(path.join(r,'framework/templates/analysis.md'),'# {{company}}：{{title}}\n');return r;}
test('文档持久化、公司隔离、上下文快照、历史保护及追加验证',t=>{const root=fixture(t),lib=createLibrary(root);lib.createCompany({slug:'sample',name:'样本',ticker:'0001',sector:'测试'});const report=lib.createAnalysis({company:'sample',title:'增长驱动',date:'2026-10-21'}),base=report.slice(0,-10);const context=lib.read(base+'/context.md').content;const shared='companies/sample/knowledge/methods.md',d=lib.read(shared);lib.save(shared,'# 新方法\n证据先行',d.digest);assert.equal(lib.read(base+'/context.md').content,context);assert.match(createLibrary(root).read(shared).content,/证据先行/);assert.throws(()=>lib.save(shared,'覆盖',d.digest),e=>e.status===409);const draft=lib.read(report);lib.save(report,draft.content+'\n补充判断',draft.digest);fs.writeFileSync(path.join(root,report),frontmatter({status:'snapshot',asOf:'2026-10-21',title:'留档'},'# 历史判断'));assert.throws(()=>lib.save(report,'覆盖',lib.read(report).digest),e=>e.status===403);const v=base+'/verification.md',old=lib.read(v);lib.appendVerification({relative:v,expected:old.digest,question:'增长可持续？',observation:'尚缺可比口径。',source:'https://example.com/filing',outcome:'未解决'});assert.ok(lib.read(v).content.startsWith(old.content));assert.equal(lib.catalog().counts.analyses,1);assert.ok(lib.search('尚缺可比').some(d=>d.path===v));assert.throws(()=>lib.createCompany({slug:'sample',name:'重复'}),e=>e.status===409);assert.throws(()=>lib.createAnalysis({company:'sample',title:'错日期',date:'2026-02-31'}),e=>e.status===400);});
test('路径与符号链接拒绝越界，Markdown 不执行脚本',t=>{const root=fixture(t),lib=createLibrary(root);for(const p of ['../private.md','/etc/passwd','companies/../README.md','x\\y.md'])assert.throws(()=>lib.read(p));fs.symlinkSync('/etc',path.join(root,'outside'));assert.throws(()=>lib.read('outside/passwd.md'),e=>e.status===403);const h=renderMarkdown('# 标题\n<script>alert(1)</script>\n[危险](javascript:alert(1))\n[安全](https://example.com)');assert.ok(!h.includes('<script>'));assert.ok(!h.includes('href="javascript:'));assert.match(h,/href="https:\/\/example.com/);});
test('HTTP 完整创建/保存/重启读取与来源校验',async t=>{const root=fixture(t),server=createServer(root);await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>server.close());const origin='http://127.0.0.1:'+server.address().port;const get=async p=>(await fetch(origin+'/api/'+p)).json();const c=await get('catalog');const post=(p,body,token=c.csrf,from=origin)=>fetch(origin+'/api/'+p,{method:'POST',headers:{Origin:from,'Content-Type':'application/json','X-Research-Token':token},body:JSON.stringify(body)});assert.equal((await post('companies',{slug:'web',name:'网页公司',ticker:'HK',sector:'测试'})).status,201);const p=await(await post('analyses',{company:'web',title:'接口研究',date:'2026-10-21'})).json();assert.ok(p.path);const d=await get('document?path='+encodeURIComponent(p.path));assert.equal((await post('save',{path:p.path,expected:d.digest,content:d.content+'\n持久化'})).status,200);assert.match(createLibrary(root).read(p.path).content,/持久化/);assert.equal((await post('companies',{slug:'evil',name:'越界'},'bad')).status,403);assert.equal((await post('companies',{slug:'evil',name:'越界'},c.csrf,'https://evil.example')).status,403);assert.equal((await fetch(origin+'/healthz')).status,200);for(const url of ['/','/app.js','/style.css'])assert.equal((await fetch(origin+url)).status,200);});


test('PDF本地资源与固定发布摘要一致',()=>{
 const dir=new URL('./public/vendor/',import.meta.url);const manifest=JSON.parse(fs.readFileSync(new URL('manifest.json',dir),'utf8'));const packed=JSON.parse(fs.readFileSync(new URL('assets.json',dir),'utf8'));
 assert.equal(manifest.version,'6.4.299');
 for(const [name,digest] of Object.entries(manifest.assets)){
  const bytes=Object.hasOwn(packed,name)?Buffer.from(packed[name],'base64'):fs.readFileSync(new URL(name.split('/').pop(),dir));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),digest,name);
 }
});
test('PDF页面、下载原件、资源类型和路径拒绝',async t=>{
 const root=fixture(t),dir=path.join(root,'companies/sample/sources');fs.mkdirSync(dir,{recursive:true});const bytes=Buffer.from('%PDF-1.4\nPDF test bytes\n%%EOF');fs.writeFileSync(path.join(dir,'sample.pdf'),bytes);
 const server=createServer(root);await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>server.close());const origin='http://127.0.0.1:'+server.address().port;
 for(const resource of ['/pdf?path=companies/sample/sources/sample.pdf','/pdf-viewer.js','/pdf-viewer.css','/vendor/pdf.min.mjs','/vendor/pdf.worker.min.mjs'])assert.equal((await fetch(origin+resource)).status,200,resource);
 const result=await fetch(origin+'/api/attachment?path=companies/sample/sources/sample.pdf&download=1');assert.equal(result.headers.get('content-type'),'application/pdf');assert.match(result.headers.get('content-disposition'),/^attachment/);assert.deepEqual(Buffer.from(await result.arrayBuffer()),bytes);
 for(const resource of ['/api/attachment?path=../private.pdf','/vendor/%2e%2e/server.js','/vendor/not-a-file'])assert.ok((await fetch(origin+resource)).status>=400);
 const missing=await fetch(origin+'/api/attachment?path=companies/sample/sources/missing.pdf');assert.ok(missing.status>=400);
});

// Exercise the actual executable entry: imports alone do not catch hosting failures.
test('正式启动参数无需配置环境引用即可读取资料', {timeout:10000}, async t=>{
 const root=fixture(t);const env={...process.env,PORT:'0'};delete env.INVESTMENT_LIBRARY_ROOT;
 const child=spawn(process.execPath,[new URL('./server.js',import.meta.url).pathname,'--library-root',root],{env,stdio:['ignore','pipe','pipe']});
 const stopped=new Promise(resolve=>child.once('exit',resolve));
 t.after(async()=>{child.kill('SIGTERM');await stopped;});
 const origin=await new Promise((resolve,reject)=>{let output='';child.on('error',reject);child.once('exit',code=>reject(new Error('server exited '+code)));child.stdout.on('data',chunk=>{output+=chunk;const m=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(m)resolve(m[0]);});});
 const health=await(await fetch(origin+'/healthz')).json();assert.equal(health.version,'1.2.0');assert.equal(health.status,'ready');
 const doc=await(await fetch(origin+'/api/document?path=README.md')).json();assert.match(JSON.stringify(doc),/原始内容/);
});

test('项目结构兼容旧入口且源码不进入资料索引',t=>{
 const root=fixture(t),lib=createLibrary(root);fs.mkdirSync(path.join(root,'industries/smartphones'),{recursive:true});fs.writeFileSync(path.join(root,'industries/smartphones/methodology.md'),'# 手机行业方法');
 fs.mkdirSync(path.join(root,'apps/research-web'),{recursive:true});fs.writeFileSync(path.join(root,'apps/research-web/README.md'),'应用源码说明');
 assert.equal(lib.read('rules.md').content,lib.read('framework/rules.md').content);assert.equal(lib.read('playbooks/smartphones.md').content,lib.read('industries/smartphones/methodology.md').content);
 lib.createCompany({slug:'alias',name:'兼容验证'});assert.equal(lib.read('companies/alias/shared/profile.md').content,lib.read('companies/alias/knowledge/profile.md').content);
 assert.ok(!lib.files().some(x=>x.startsWith('apps/')));const report=lib.createAnalysis({company:'alias',title:'新结构',date:'2026-10-21'});const context=lib.read(report.replace('report.md','context.md')).content;assert.match(context,/industries\/smartphones\/methodology.md/);assert.match(context,/companies\/alias\/knowledge\/profile.md/);
});
