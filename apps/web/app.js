"use strict";
const $ = id => document.getElementById(id);
let catalog = {entries: [], sources: []};
let planId = null;
let busy = false;
const labels = {status:"状态", complete:"完整", partial:"部分覆盖", blocked:"已阻断", review_required:"待人工审核", planned:"计划已生成", ok:"成功", date:"日期", trade_date:"交易日", security_id:"证券", company_id:"公司", source_id:"来源", document_id:"资料编号", open:"开盘价", high:"最高价", low:"最低价", close:"收盘价", volume:"成交量", currency:"币种", price_basis:"价格口径", published_at:"公开时间", observed_at:"采集时间", registered_at:"登记时间", metric_id:"财务项目", value:"数值", unit:"单位", period_start:"期间开始", period_end:"期间结束", scope:"报表范围", evidence_refs:"证据引用", provenance:"来源追溯", dataset_id:"数据类型", record_id:"记录编号", report_document_id:"报告原件", unadjusted:"已核实不复权", "provider-native":"供应商原生口径", reason:"原因"};
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
  finally { busy = false; document.querySelectorAll("button").forEach(button => button.disabled = false); $("apply").disabled = !planId; }
}
function scope() {
  const payload = {dataset_id: $("dataset").value, subject_id: $("subject").value, start: $("start").value, end: $("end").value, knowledge_mode: $("mode").value};
  if (payload.dataset_id === "financial-facts") payload.subject_id = catalog.securities.find(item => item.id === payload.subject_id)?.company_id || payload.subject_id;
  payload.price_basis = $("price-basis").value;
  if (!payload.subject_id || !payload.start || !payload.end) throw new Error("请选择研究证券和完整日期区间。");
  if (payload.start > payload.end) throw new Error("起始日期不能晚于结束日期。");
  if ($("cutoff").value) payload.information_cutoff = new Date($("cutoff").value).toISOString();
  else if (payload.knowledge_mode !== "retrospective_explanation") throw new Error("历史信息模式需要填写信息截止时间。");
  return payload;
}
function gapRequest() {
  const payload = scope();
  if (!$("expectation").value) throw new Error("尚无已登记的预期清单，不能推断完整性。请先登记交易日或披露预期。");
  payload.expectation_path = $("expectation").value;
  if ($("source").value) payload.source_id = $("source").value;
  return payload;
}
function coverageSummary(value) {
  const coverage = value.coverage || {};
  const lines = [`状态：${label(value.status)}`, `已有记录：${value.record_count ?? coverage.present_count ?? coverage.observed_records ?? "未统计"}`];
  if (coverage.expected_count !== undefined) lines.push(`预期记录：${coverage.expected_count}`);
  const gaps = value.gaps || coverage.gaps;
  if (gaps) lines.push(`缺口：${JSON.stringify(gaps)}`);
  if (coverage.completeness === "unknown_without_expected_calendar") lines.push("完整性未知：尚未按预期交易日清单核查。");
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
  renderRecords(value.rows || []); coverageSummary(value); message("已读取本地归档数据，未触发采集。");
}
function options(id, entries, placeholder, valueKey = "id") {
  const selected = $(id).value;
  $(id).replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = placeholder; $(id).append(empty);
  for (const entry of entries) { const option = document.createElement("option"); option.value = entry[valueKey]; option.textContent = entry.name; $(id).append(option); }
  if (entries.some(entry => entry[valueKey] === selected)) $(id).value = selected;
  else if (entries.length === 1) $(id).value = entries[0][valueKey];
}
function showSource() { const source = catalog.sources.find(item => item.id === $("source").value); $("source-notes").textContent = (source?.limitations || []).join("；"); }
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
  options("subject", catalog.securities.filter(item => item.confirmed), "选择已确认的主证券");
  filterChoices();
  showSource(); renderFiles(); $("connection").textContent = "本地服务已连接";
  if (catalog.truncated) message("目录较大，仅展示前 2000 个文件；请通过 CLI 查询完整档案。");
}
function expectationDates() {
  const entry = catalog.expectations.find(item => item.path === $("expectation").value);
  if (entry) { $("start").value = entry.start; $("end").value = entry.end; }
}
function filterChoices() {
  const dataset = $("dataset").value;
  const security = $("subject").value;
  const subject = dataset === "financial-facts" ? catalog.securities.find(item => item.id === security)?.company_id : security;
  options("source", catalog.sources.filter(item => item.dataset_id === dataset && (!item.security_id || item.security_id === security)), "选择来源");
  options("expectation", catalog.expectations.filter(item => item.dataset_id === dataset && item.subject_id === subject), "选择预期清单", "path");
  if (!$("expectation").value && $("expectation").options.length > 1) $("expectation").selectedIndex = 1;
  expectationDates(); showSource();
  $("price-basis").disabled = dataset !== "daily-prices";
}
$("dataset").addEventListener("change", filterChoices);
$("subject").addEventListener("change", filterChoices);
$("expectation").addEventListener("change", expectationDates);
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
