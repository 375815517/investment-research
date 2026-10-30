"use strict";
const $ = id => document.getElementById(id);
let catalog = {entries: [], sources: []};
let planId = null;
let busy = false;
const labels = {status:"状态", complete:"完整", partial:"部分覆盖", blocked:"已阻断", review_required:"待人工审核", planned:"计划已生成", ok:"成功", date:"日期", trade_date:"交易日", security_id:"证券", company_id:"公司", source_id:"来源", document_id:"资料编号", open:"开盘价", high:"最高价", low:"最低价", close:"收盘价", volume:"成交量", currency:"币种", price_basis:"价格口径", published_at:"公开时间", observed_at:"采集时间", registered_at:"登记时间", metric_id:"财务项目", value:"数值", unit:"单位", period_start:"期间开始", period_end:"期间结束", scope:"报表范围", evidence_refs:"证据引用", provenance:"来源追溯", dataset_id:"数据类型", record_id:"记录编号", report_document_id:"报告原件", unadjusted:"已核实不复权", "provider-native":"供应商原生口径", reason:"原因"};
Object.assign(labels, {event_date:"事件日期", subject_id:"研究对象", subject_type:"对象类别", document_kind:"资料类别", source_category:"来源类别", statement:"来源陈述", excerpt:"原文摘录", evidence_quote:"原文证据", locator:"原文位置", basis:"数据口径", quote:"引文", metric_id:"字段／项目", document_refs:"原件引用", batch_refs:"入库批次", policy:"政策", industry:"行业", news:"新闻", company:"公司", jurisdiction:"司法辖区", event:"事件", snapshot:"时间快照"});
function supportedGaps() { return ["daily-prices", "financial-facts"].includes($("dataset").value); }
function syncButtons() { for (const id of ["check-gaps", "plan"]) $(id).disabled = busy || !supportedGaps(); $("apply").disabled = busy || !planId; }
Object.assign(labels, {ready:"在声明范围内适用", limited:"有限适用"});
const label = key => labels[key] || key;

async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json", "X-Research-Client": "data-ui"}, body: JSON.stringify(payload)
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.summary || value.detail || value.issues?.[0]?.message || `请求失败 ${response.status}`);
  return value;
}
function message(text, error = false) { $("message").textContent = text; $("message").className = "message" + (error ? " error" : ""); }
async function run(action) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach(button => button.disabled = true);
  message("处理中…");
  try { await action(); } catch (error) { message(error.message, true); }
  finally { busy = false; document.querySelectorAll("button").forEach(button => button.disabled = false); syncButtons(); }
}
function scope() {
  const payload = {dataset_id: $("dataset").value, subject_id: $("subject").value, start: $("start").value, end: $("end").value, knowledge_mode: $("mode").value};
  if (payload.dataset_id === "daily-prices") payload.price_basis = $("price-basis").value;
  if ($("source").value) payload.source_id = $("source").value;
  if (!payload.subject_id || !payload.start || !payload.end) throw new Error("请选择研究对象和完整日期区间。");
  if (payload.start > payload.end) throw new Error("起始日期不能晚于结束日期。");
  if ($("cutoff").value) payload.information_cutoff = new Date($("cutoff").value).toISOString();
  else if (payload.knowledge_mode !== "retrospective_explanation") throw new Error("历史信息模式需要填写信息截止时间。");
  return payload;
}
function gapRequest() {
  if (!supportedGaps()) throw new Error("此类数据尚无完整性契约，仅可查询已归档渠道记录，不能自动推断或补齐所有信息。");
  const payload = scope();
  if (!$("expectation").value) throw new Error("尚无已登记的预期清单，不能推断完整性。请先登记交易日或披露预期。");
  payload.expectation_path = $("expectation").value;
  if ($("source").value) payload.source_id = $("source").value;
  return payload;
}
function coverageSummary(value) {
  const coverage = value.coverage || {};
  const lines = [`状态：${label(value.status)}`, `已有记录：${value.record_count ?? coverage.present_count ?? coverage.observed_records ?? "未统计"}`];
  if (value.date_semantics) lines.push(`时间筛选口径：${value.date_semantics}`);
  if (coverage.expected_count !== undefined) lines.push(`预期记录：${coverage.expected_count}`);
  const gaps = value.gaps || coverage.gaps;
  if (gaps) lines.push(`缺口：${JSON.stringify(gaps)}`);
  if (coverage.completeness === "unknown_without_expected_calendar") lines.push("完整性未知：尚未按预期交易日清单核查。");
  if (!supportedGaps()) lines.push("完整性未知：当前结果仅代表已归档渠道；不代表全部市场信息或全部政策、报道。");
  if (value.source_counts) lines.push(`按来源记录数：${JSON.stringify(value.source_counts)}`);
  for (const issue of value.issues || []) lines.push(`${issue.code}: ${issue.message || ""}`);
  $("coverage-summary").textContent = lines.join("\n");
}
function renderRecords(rows) {
  $("records").replaceChildren();
  $("record-count").textContent = `${rows.length} 条`;
  if (!rows.length) { const p = document.createElement("p"); p.className = "empty"; p.textContent = "所选条件下没有可用记录；缺失未被填为零。"; $("records").append(p); return; }
  const columns = [...new Set(rows.flatMap(Object.keys))];
  const table = document.createElement("table");
  const head = document.createElement("thead"), header = document.createElement("tr");
  for (const key of columns) { const th = document.createElement("th"); th.scope = "col"; th.textContent = label(key); th.title = key; header.append(th); }
  head.append(header); table.append(head);
  const body = document.createElement("tbody");
  for (const row of rows) { const tr = document.createElement("tr"); for (const key of columns) { const td = document.createElement("td"); td.textContent = typeof row[key] === "object" ? JSON.stringify(row[key]) : label(String(row[key] ?? "")); tr.append(td); } body.append(tr); }
  table.append(body); $("records").append(table);
}
async function query() {
  const value = await api("/api/coverage?" + new URLSearchParams(scope()));
  renderRecords(value.rows || []); renderEvidence(value); coverageSummary(value); message("已读取本地归档数据，未触发采集。");
}
function renderEvidence(value) {
  $("evidence-links").replaceChildren();
  const rowRefs = (value.rows || []).flatMap(row => [...(row.document_refs || []), ...(row.batch_refs || [])]);
  const identifiers = [...(value.document_refs || []), ...(value.batch_refs || []), ...(value.artifact_refs || []), ...rowRefs].filter(item => typeof item === "string");
  const paths = identifiers.flatMap(ref => ref.startsWith("data/") || ref.startsWith("research/") ? [ref] : catalog.entries.filter(item => item.path.split("/").includes(ref) && /\/original\.[^/]+$/.test(item.path)).map(item => item.path));
  const refs = [...new Set(paths)];
  for (const ref of refs) { const link = document.createElement("a"); link.textContent = "复核归档：" + ref; link.href = "/api/files?" + new URLSearchParams({path: ref, download: "true"}); link.style.display = "block"; $("evidence-links").append(link); }
}
function options(id, entries, placeholder, valueKey = "id") {
  const selected = $(id).value;
  $(id).replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = placeholder; $(id).append(empty);
  for (const entry of entries) { const option = document.createElement("option"); option.value = entry[valueKey]; option.textContent = entry.name; $(id).append(option); }
  if (entries.some(entry => entry[valueKey] === selected)) $(id).value = selected;
  else if (entries.length === 1) $(id).value = entries[0][valueKey];
}
function showSource() { const source = catalog.sources.find(item => item.id === $("source").value); $("source-notes").textContent = [source ? `来源类别：${label(source.category || "未登记")}；渠道：${source.name}` : "未限定来源：不同渠道记录分别返回，不进行跨来源合并。", ...(source?.limitations || [])].join("；"); }
function renderFiles() {
  const search = $("file-search").value.toLowerCase();
  $("files").replaceChildren();
  for (const item of catalog.entries.filter(item => item.path.toLowerCase().includes(search)).slice(0, 300)) {
    const li = document.createElement("li"), button = document.createElement("button"); button.type = "button"; button.textContent = item.path;
    button.addEventListener("click", () => run(async () => { const value = await api("/api/files?" + new URLSearchParams({path: item.path})); $("preview-title").textContent = item.path; $("preview-content").textContent = value.preview ?? value.reason ?? "此格式无法文本预览，可下载原件。"; $("download").href = "/api/files?" + new URLSearchParams({path: item.path, download: "true"}); $("download").hidden = false; message("已打开归档文件。"); })); li.append(button); $("files").append(li);
  }
}
async function loadCatalog() {
  catalog = await api("/api/catalog");
  options("audit-policy", catalog.audits || [], "选择已登记需求清单", "path");
  refreshSubjects();
  showSource(); renderFiles(); $("connection").textContent = "本地服务已连接";
  if (catalog.truncated) message("目录较大，仅展示前 2000 个文件；请通过 CLI 查询完整档案。");
}
function expectationDates() {
  const entry = catalog.expectations.find(item => item.path === $("expectation").value);
  if (entry) { $("start").value = entry.start; $("end").value = entry.end; }
}
function refreshSubjects() {
  const dataset = $("dataset").value;
  let entries = catalog.securities.filter(item => item.confirmed);
  if (["financial-facts", "document-facts"].includes(dataset)) entries = entries.filter(item => item.company_id).map(item => ({id:item.company_id, name:item.company_id === "xiaomi" ? "小米集团（公司）" : item.company_id}));
  for (const source of catalog.sources.filter(item => item.dataset_id === dataset && item.subject_id)) entries.push({id:source.subject_id, name:`${source.subject_id}（${label(source.subject_type || "研究对象")}）`});
  entries = [...new Map(entries.map(item => [item.id, item])).values()];
  options("subject", entries, "选择研究对象");
  filterChoices();
}
function filterChoices() {
  const dataset = $("dataset").value;
  const subject = $("subject").value;
  const security = catalog.securities.find(item => item.id === subject || item.company_id === subject)?.id;
  options("source", catalog.sources.filter(item => item.dataset_id === dataset && (!item.security_id || item.security_id === security) && (!item.subject_id || item.subject_id === subject)), "全部已归档渠道／补采时选来源");
  options("expectation", catalog.expectations.filter(item => item.dataset_id === dataset && item.subject_id === subject), "选择预期清单", "path");
  if (!$("expectation").value && $("expectation").options.length > 1) $("expectation").selectedIndex = 1;
  expectationDates(); showSource();
  $("price-basis").disabled = dataset !== "daily-prices";
  $("expectation").disabled = !supportedGaps();
  const notes = {"daily-prices":"日期按交易日筛选；价格口径需明确。", "financial-facts":"日期按财报期间结束日筛选；公开时间和采集时间另外保留。", "market-observations":"含时刻的观测按 UTC 日期筛选，只有日期的观测保留来源日期；不等同于香港交易日。这是供应商时间快照，不推断为历史时点指标。单位与口径分别保留，完整性未知。", "document-facts":"日期按事件日期筛选；保存来源陈述与原文证据，不等同于已证实事实。公开、采集和登记时间分别保留；完整性未知。"};
  $("dataset-notes").textContent = notes[dataset] || "";
  syncButtons();
}
$("dataset").addEventListener("change", refreshSubjects);
$("subject").addEventListener("change", filterChoices);
$("expectation").addEventListener("change", expectationDates);
async function auditRequest() {
  if (!$("audit-policy").value) throw new Error("请选择已登记的明确需求清单。");
  const file = await api("/api/files?" + new URLSearchParams({path: $("audit-policy").value}));
  if (!file.preview) throw new Error("需求清单无法读取。");
  return JSON.parse(file.preview);
}
$("audit").addEventListener("click", () => run(async () => {
  const result = await api("/api/audit-inputs", await auditRequest());
  $("audit-output").textContent = JSON.stringify(result, null, 2);
  const satisfied = (result.results || []).filter(item => item.status === "satisfied").length;
  $("audit-summary").textContent = `已满足 ${satisfied} / ${(result.results || []).length} 项声明样本需求。范围仅限当前清单，不代表信息全量完整。`;
  message("已完成只读输入核查，未采集数据。");
}));
$("assess").addEventListener("click", () => run(async () => {
  const request = await auditRequest();
  request.purpose = $("assessment-purpose").value;
  request.knowledge_mode = $("mode").value;
  delete request.information_cutoff;
  if ($("cutoff").value) request.information_cutoff = new Date($("cutoff").value).toISOString();
  if (request.purpose === "historical_point_in_time" && request.knowledge_mode === "retrospective_explanation") throw new Error("历史时点用途需要选择模拟历史公开信息或复现当时实际掌握的信息。");
  if (request.knowledge_mode !== "retrospective_explanation" && !request.information_cutoff) throw new Error("历史信息模式需要填写信息截止时间。");
  const result = await api("/api/assess-inputs", request);
  $("assessment-output").textContent = JSON.stringify(result, null, 2);
  $("assessment-summary").textContent = `适用性：${label(result.status)}。仅评估所选清单与用途；全历史完整性仍需单独核实。`;
  $("assessment-findings").replaceChildren();
  for (const finding of result.findings || []) {
    const item = document.createElement("li");
    item.textContent = `${finding.code}: ${finding.message || finding.reason || JSON.stringify(finding)}`;
    $("assessment-findings").append(item);
  }
  message("已完成只读适用性评估，未采集或修改数据。");
}));
$("scope-form").addEventListener("submit", event => { event.preventDefault(); run(query); });
$("source").addEventListener("change", showSource);
$("file-search").addEventListener("input", renderFiles);
$("reload").addEventListener("click", () => run(async () => { await loadCatalog(); message("目录已刷新。"); }));
$("check-gaps").addEventListener("click", () => run(async () => { const value = await api("/api/gaps", gapRequest()); coverageSummary(value); $("plan-output").textContent = JSON.stringify(value, null, 2); message("缺口检查完成，未执行采集。"); }));
$("plan").addEventListener("click", () => run(async () => { planId = null; const value = await api("/api/ensure/plan", gapRequest()); planId = value.plan_id || null; $("plan-output").textContent = JSON.stringify(value, null, 2); $("plan-details").open = true; coverageSummary(value); message(planId ? "补采计划已生成。检查详情后可应用。" : "未生成可执行计划，请查看阻断原因。"); }));
$("apply").addEventListener("click", () => run(async () => { if (!planId) return; const current = planId; planId = null; const value = await api("/api/ensure/apply", {plan_id: current}); $("plan-output").textContent = JSON.stringify(value, null, 2); $("plan-details").open = true; await loadCatalog(); await query(); message(`计划执行结果：${label(value.status)}。请查看执行详情与剩余缺口。`); }));
for (const id of ["subject", "dataset", "price-basis", "start", "end", "mode", "cutoff", "source", "expectation"]) $(id).addEventListener("change", () => { planId = null; $("apply").disabled = true; });
const today = new Date(); $("end").value = today.toISOString().slice(0, 10); $("start").value = new Date(today.getTime() - 30 * 86400000).toISOString().slice(0, 10);
run(async () => { await loadCatalog(); message("选择研究范围后查询。采集只在应用计划时执行。"); });
