// Render a deliberately small, escaped Markdown subset. Source HTML is never executed.
export const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function splitDocument(content) {
  const meta = {};
  if (!content.startsWith('---\n')) return { meta, body: content };
  const end = content.indexOf('\n---\n', 4);
  if (end < 0) return { meta, body: content };
  for (const line of content.slice(4, end).split('\n')) {
    const match = /^([a-zA-Z][\w-]*):\s*(.*)$/.exec(line);
    if (!match) continue;
    try { meta[match[1]] = JSON.parse(match[2]); } catch { meta[match[1]] = match[2]; }
  }
  return { meta, body: content.slice(end + 5) };
}
export function renderMarkdown(input, documentPath = '') {
  const inline = text => {
    const slots = [];
    const hold = html => `\u0000${slots.push(html) - 1}\u0000`;
    let s = escapeHTML(text).replace(/`([^`]+)`/g, (_, x) => hold(`<code>${x}</code>`));
    s = s.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (_, label, raw) => {
      const href = raw.replace(/&amp;/g, '&');
      if (/^https?:\/\//i.test(href)) return hold(`<a href="${escapeHTML(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`);
      if (documentPath && !/[:\\?#]/.test(href) && !href.startsWith('/') && /\.(md|csv|json|pdf)$/.test(href)) {
        const parts = documentPath.split('/').slice(0,-1);
        for (const part of href.split('/')) { if(part==='..') { if(!parts.length)return label; parts.pop(); } else if(part!=='.')parts.push(part); }
        const target=parts.join('/');
        const url=target.endsWith('.pdf')?'/pdf?path='+encodeURIComponent(target)+'&from='+encodeURIComponent(documentPath):'#doc/'+encodeURIComponent(target);
        return hold(`<a href="${escapeHTML(url)}">${label}</a>`);
      }
      return label;
    });
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => slots[Number(i)]);
  };
  const lines = splitDocument(input).body.replace(/\r/g, '').split('\n');
  const out = []; let inCode = false, code = [], list = false;
  const closeList = () => { if (list) { out.push('</ul>'); list = false; } };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^```/.test(line)) { closeList(); if (inCode) out.push(`<pre><code>${escapeHTML(code.join('\n'))}</code></pre>`); inCode = !inCode; code = []; continue; }
    if (inCode) { code.push(line); continue; }
    if (/^\s*\|/.test(line) && /^\s*\|?\s*:?-{3}/.test(lines[i + 1] || '')) {
      closeList(); const cells = x => x.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
      out.push('<div class="table-scroll"><table><thead><tr>' + cells(line).map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>'); i++;
      while (/^\s*\|/.test(lines[i + 1] || '')) out.push('<tr>' + cells(lines[++i]).map(c => `<td>${c}</td>`).join('') + '</tr>');
      out.push('</tbody></table></div>'); continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) { closeList(); const n = Math.min(heading[1].length + 1, 6); out.push(`<h${n}>${inline(heading[2])}</h${n}>`); continue; }
    const item = /^\s*[-*]\s+(.*)$/.exec(line);
    if (item) { if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(item[1]).replace(/^\[ \]/, '<span class="check-open" aria-label="待验证">□</span>').replace(/^\[[xX]\]/, '<span aria-label="已记录">✓</span>')}</li>`); continue; }
    closeList();
    if (line.startsWith('>')) out.push(`<blockquote>${inline(line.replace(/^>\s?/, ''))}</blockquote>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  closeList(); if (inCode) out.push(`<pre><code>${escapeHTML(code.join('\n'))}</code></pre>`);
  return out.join('\n');
}
