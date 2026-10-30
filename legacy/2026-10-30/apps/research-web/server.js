import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';
import { createLibrary, fail } from './lib/store.js';
const directory = path.dirname(fileURLToPath(import.meta.url));
// Fixed, local PDF.js assets are indexed at startup; request paths never become filesystem paths.
const pdfAssets = JSON.parse(fs.readFileSync(path.join(directory, 'public/vendor/assets.json'), 'utf8'));
const assetType = name => name.endsWith('.wasm') ? 'application/wasm' : name.endsWith('.ttf') ? 'font/ttf' : name.endsWith('.mjs') ? 'text/javascript; charset=utf-8' : 'application/octet-stream';
export function createServer(root) {
  const library = createLibrary(root); const csrf = randomBytes(32).toString('hex');
  const server = http.createServer(async (req, res) => {
    const send = (code, data, type = 'application/json; charset=utf-8') => { res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; font-src 'self' data: blob:; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self' http://127.0.0.1:* http://localhost:*; base-uri 'none'; form-action 'self'" }); res.end(type.startsWith('application/json') ? JSON.stringify(data) : data); };
    try {
      const host = req.headers.host || ''; if (!/^(127\.0\.0\.1|localhost):\d+$/.test(host)) throw fail('只允许本机访问。', 403);
      const url = new URL(req.url, `http://${host}`);
      if (req.method === 'GET') {
        if (url.pathname === '/healthz') { library.read('README.md'); return send(200, { status: 'ready', version: '1.2.0' }); }
        if (url.pathname === '/api/catalog') return send(200, { ...library.catalog(), csrf });
        if (url.pathname === '/api/market') return send(200, library.market());
        if (url.pathname === '/api/attachment') {
          const relative = url.searchParams.get('path') || '';
          const bytes = library.attachment(relative);
          if (url.searchParams.get('download') === '1') res.setHeader('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(path.basename(relative))}`);
          return send(200, bytes, 'application/pdf');
        }
        if (url.pathname === '/api/document') return send(200, library.document(url.searchParams.get('path')));
        if (url.pathname === '/api/search') return send(200, { results: library.search(url.searchParams.get('q') || '') });
        if (url.pathname === '/api/download') { const d = library.read(url.searchParams.get('path')); res.setHeader('Content-Disposition', `attachment; filename="${path.basename(d.path)}"`); return send(200, d.content, 'text/plain; charset=utf-8'); }
        const staticFiles = { '/': ['index.html', 'text/html; charset=utf-8'], '/app.js': ['app.js', 'text/javascript; charset=utf-8'], '/style.css': ['style.css', 'text/css; charset=utf-8'] };
        Object.assign(staticFiles, { '/pdf': ['pdf-viewer.html', 'text/html; charset=utf-8'], '/pdf-viewer.js': ['pdf-viewer.js', 'text/javascript; charset=utf-8'], '/pdf-viewer.css': ['pdf-viewer.css', 'text/css; charset=utf-8'], '/vendor/pdf.min.mjs': ['vendor/pdf.min.mjs', 'text/javascript; charset=utf-8'], '/vendor/pdf.worker.min.mjs': ['vendor/pdf.worker.min.mjs', 'text/javascript; charset=utf-8'] });
        const assetName = url.pathname.startsWith('/vendor/') ? url.pathname.slice(8) : '';
        if (Object.hasOwn(pdfAssets, assetName)) return send(200, Buffer.from(pdfAssets[assetName], 'base64'), assetType(assetName));
        const file = staticFiles[url.pathname]; if (file) return send(200, fs.readFileSync(path.join(directory, 'public', file[0])), file[1]);
        throw fail('未找到页面。', 404);
      }
      if (req.method !== 'POST') throw fail('不支持的操作。', 405);
      if (req.headers.origin !== `http://${host}` || req.headers['x-research-token'] !== csrf || !req.headers['content-type']?.startsWith('application/json')) throw fail('写入来源校验失败，请刷新页面后重试。', 403);
      let text = ''; for await (const chunk of req) { text += chunk; if (Buffer.byteLength(text) > 1100000) throw fail('请求内容过大。', 413); }
      let body; try { body = JSON.parse(text); } catch { throw fail('请求内容不是有效 JSON。'); }
      if (url.pathname === '/api/save') return send(200, library.save(body.path, body.content, body.expected));
      if (url.pathname === '/api/companies') return send(201, { company: library.createCompany(body) });
      if (url.pathname === '/api/analyses') return send(201, { path: library.createAnalysis(body) });
      if (url.pathname === '/api/verification') return send(200, library.appendVerification(body));
      throw fail('未找到操作。', 404);
    } catch (error) { send(error.status || 500, { error: error.status ? error.message : '读取或保存失败，请检查资料目录与文档格式。' }); }
  });
  return server;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const rootOption = process.argv.indexOf('--library-root');
  const root = rootOption >= 0 ? process.argv[rootOption + 1] : process.env.INVESTMENT_LIBRARY_ROOT;
  if (!root || !path.isAbsolute(root)) { console.error('请通过 --library-root 或 INVESTMENT_LIBRARY_ROOT 指定资料目录绝对路径。'); process.exitCode = 1; }
  else {
    const server = createServer(root);
    server.listen(Number(process.env.PORT || 0), '127.0.0.1', () => console.log(`研习 http://127.0.0.1:${server.address().port}`));
    for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
  }
}
