// Optional local package only; the project owns all application source.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const files=['APP.yaml','README.md','package.json','server.js','test.js','lib/store.js','lib/markdown.js','public/app.js','public/style.css','public/index.html','public/pdf-viewer.html','public/pdf-viewer.js','public/pdf-viewer.css','public/vendor/pdf.min.mjs','public/vendor/pdf.worker.min.mjs','public/vendor/LICENSE','public/vendor/assets.json','public/vendor/manifest.json'];
const target=path.join(root,'.build/research-web');
for(const name of files){const dest=path.join(target,name);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(path.join(root,'apps/research-web',name),dest);}
console.log('已生成项目内 .build/research-web；未接入、安装或启动 Oriel 应用。');
