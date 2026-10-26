import {getDocument, GlobalWorkerOptions} from '/vendor/pdf.min.mjs';
GlobalWorkerOptions.workerSrc='/vendor/pdf.worker.min.mjs';
const $=id=>document.getElementById(id);
const query=new URLSearchParams(location.search),relative=query.get('path')||'';
const source='/api/attachment?path='+encodeURIComponent(relative);
const from=query.get('from')||'';
if (/^[\w/.-]+\.(md|csv|json)$/.test(from) && !from.split('/').includes('..')) $('return').href='/#doc/'+encodeURIComponent(from);
$('title').textContent=relative.split('/').pop()||'财报原件';
$('download').href=source+'&download=1';
let pdf=null,current=1,renderTask=null,revision=0,resizeTimer;
function controls(busy){for(const id of ['page','go','zoom'])$(id).disabled=busy||!pdf;$('prev').disabled=busy||!pdf||current<=1;$('next').disabled=busy||!pdf||current>=pdf.numPages;}
function showError(message){$('status').textContent='未能显示原件';$('error').textContent=message;$('error').hidden=false;$('retry').hidden=false;}
async function render(number){
 if(!pdf)return;
 const token=++revision;renderTask?.cancel();current=Math.max(1,Math.min(pdf.numPages,number));controls(true);$('page').value=current;$('status').textContent=`正在显示第 ${current} 页…`;$('error').hidden=true;$('canvas').hidden=true;$('text-panel').hidden=true;
 try{
  const page=await pdf.getPage(current);if(token!==revision)return;
  const unscaled=page.getViewport({scale:1});const width=Math.max(240,$('sheet').clientWidth-24);
  const scale=$('zoom').value==='fit'?Math.min(2,width/unscaled.width):Number($('zoom').value);
  const viewport=page.getViewport({scale}),canvas=$('canvas'),ratio=Math.min(devicePixelRatio||1,2,Math.sqrt(16000000/(viewport.width*viewport.height)));
  canvas.width=Math.floor(viewport.width*ratio);canvas.height=Math.floor(viewport.height*ratio);canvas.style.width=viewport.width+'px';canvas.style.height=viewport.height+'px';
  renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport,transform:ratio===1?null:[ratio,0,0,ratio,0,0]});await renderTask.promise;if(token!==revision)return;
  canvas.hidden=false;canvas.setAttribute('aria-label',`PDF 第 ${current} 页，共 ${pdf.numPages} 页`);$('status').textContent=`第 ${current} / ${pdf.numPages} 页 · 已显示原件`;
  const text=await page.getTextContent();if(token!==revision)return;
  $('page-text').textContent=text.items.map(x=>x.str+(x.hasEOL?'\n':' ')).join('')||'此页没有可提取文字，请查看原件图像。';$('text-panel').hidden=false;
 }catch(error){if(error.name!=='RenderingCancelledException'&&token===revision)showError('本页渲染失败。可重新读取或下载原件。');}
 finally{if(token===revision){renderTask=null;controls(false);}}
}
async function load(){
 controls(true);$('retry').hidden=true;$('error').hidden=true;$('status').textContent='正在读取原件…';
 try{
  const response=await fetch(source);if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.error||'原件不存在或无法读取。');}
  const bytes=await response.arrayBuffer();$('download').hidden=false;
  if(pdf)await pdf.destroy();
  pdf=await getDocument({data:bytes,cMapUrl:'/vendor/cmaps/',cMapPacked:true,standardFontDataUrl:'/vendor/standard_fonts/',wasmUrl:'/vendor/wasm/',isEvalSupported:false,enableXfa:false}).promise;
  $('total').textContent='/ '+pdf.numPages;$('page').max=pdf.numPages;await render(current);
 }catch(error){pdf=null;showError(error.name==='PasswordException'?'原件受密码保护，请下载后使用已获授权的阅读器打开。':error.message||'原件读取失败。');controls(true);}
}
$('prev').onclick=()=>render(current-1);$('next').onclick=()=>render(current+1);$('jump').onsubmit=e=>{e.preventDefault();const n=Number($('page').value);if(Number.isInteger(n)&&n>=1&&n<=pdf.numPages)render(n);};$('zoom').onchange=()=>render(current);$('retry').onclick=()=>load();
addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(pdf&&$('zoom').value==='fit')render(current);},150);});
await load();
