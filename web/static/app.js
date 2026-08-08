const state = {
  db: null,
  table: null,
  columns: [],
  page: 1,
  size: 100,
  total: 0,
  mode: "data", // 'data' | 'stats'
  groupFields: [],
  sumField: null,
  hasSumCol: false,
  filterCol: null,
  filterVal: "",
};

let currentColumns = [];

const dbTree = document.getElementById("db-tree");
const emptyHint = document.getElementById("empty-hint");
const tableView = document.getElementById("table-view");
const dataTable = document.getElementById("data-table");
const selectAll = document.getElementById("select-all");
const selectAllWrap = document.getElementById("select-all-wrap");
const exportBtn = document.getElementById("export-btn");
const rowInfo = document.getElementById("row-info");
const pageInfo = document.getElementById("page-info");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const modeDataBtn = document.getElementById("mode-data");
const modeStatsBtn = document.getElementById("mode-stats");
const statsControls = document.getElementById("stats-controls");
const statsHint = document.getElementById("stats-hint");
const groupFields = document.getElementById("group-fields");
const groupAddCol = document.getElementById("group-add-col");
const groupAddBtn = document.getElementById("group-add-btn");
const sumCol = document.getElementById("sum-col");
const filterBar = document.getElementById("filter-bar");
const filterCol = document.getElementById("filter-col");
const filterVal = document.getElementById("filter-val");
const filterDate = document.getElementById("filter-date");
const filterPresets = document.getElementById("filter-presets");
const filterApply = document.getElementById("filter-apply");
const filterClear = document.getElementById("filter-clear");

const enc = encodeURIComponent;

async function loadDatabases() {
  const res = await fetch("/api/databases");
  const { databases } = await res.json();
  dbTree.innerHTML = "";
  if (!databases.length) {
    dbTree.innerHTML = '<div class="empty">暂无数据库文件</div>';
    return;
  }
  for (const db of databases) {
    dbTree.appendChild(createDbItem(db));
  }
}

function createDbItem(db) {
  const item = document.createElement("div");
  item.className = "db";

  const name = document.createElement("div");
  name.className = "db-name";
  name.innerHTML = `<span class="arrow">▶</span>📁 ${db}`;
  name.addEventListener("click", async () => {
    const isOpen = item.classList.toggle("open");
    name.classList.toggle("open", isOpen);
    if (isOpen && !item.querySelector(".db-tables").children.length) {
      await loadTables(item, db);
    }
  });

  const tables = document.createElement("div");
  tables.className = "db-tables";

  item.appendChild(name);
  item.appendChild(tables);
  return item;
}

async function loadTables(item, db) {
  const container = item.querySelector(".db-tables");
  container.innerHTML = "";
  const res = await fetch(`/api/tables?db=${enc(db)}`);
  const { tables } = await res.json();
  if (!tables.length) {
    container.innerHTML = '<div class="empty">无数据表</div>';
    return;
  }
  for (const t of tables) {
    const el = document.createElement("div");
    el.className = "table-item";
    el.textContent = t.name;
    el.title = t.name;
    el.addEventListener("click", () => {
      document.querySelectorAll(".table-item.active").forEach((n) => n.classList.remove("active"));
      el.classList.add("active");
      state.db = db;
      state.table = t.name;
      state.columns = t.columns;
      state.page = 1;
      populateStatsSelects();
      populateFilterCol();
      if (state.mode === "stats") {
        loadStats();
      } else {
        loadData();
      }
    });
    container.appendChild(el);
  }
}

function populateStatsSelects() {
  const cols = state.columns || [];
  groupAddCol.innerHTML = cols.map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`).join("");

  const numeric = cols.filter((c) => /INT|REAL|NUM|DEC|FLOA|DOUB/i.test(c.type || ""));
  const text = cols.filter((c) => !/INT|REAL|NUM|DEC|FLOA|DOUB/i.test(c.type || ""));
  const groupDefault = text.find((c) => c.name.toLowerCase().includes("user")) || text[0] || cols[0];
  state.groupFields = groupDefault ? [groupDefault.name] : [];
  const nameCol = cols.find((c) => /name|nick/i.test(c.name) && !/INT|REAL|NUM|DEC|FLOA|DOUB/i.test(c.type || ""));
  if (nameCol && !state.groupFields.includes(nameCol.name)) {
    state.groupFields.push(nameCol.name);
  }

  state.hasSumCol = numeric.length > 0;
  sumCol.innerHTML = numeric.map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`).join("");
  sumCol.disabled = !state.hasSumCol;
  const sumDefault = numeric.find((c) => c.name.toLowerCase() !== "id") || numeric[0];
  if (sumDefault) sumCol.value = sumDefault.name;
  state.sumField = state.hasSumCol ? (sumCol.value || null) : null;

  renderGroupFields();
  updateStatsControls();
}

function updateStatsControls() {
  const inStats = state.mode === "stats";
  statsControls.classList.toggle("hidden", !inStats || !state.hasSumCol);
  statsHint.classList.toggle("hidden", !inStats || state.hasSumCol);
}

function renderGroupFields() {
  groupFields.innerHTML = state.groupFields.map((f) =>
    `<span class="group-field">${escapeHtml(f)} <button type="button" class="gf-remove" data-field="${escapeHtml(f)}">×</button></span>`
  ).join("") || '<span class="group-field-empty">未选择分组字段</span>';
}

function populateFilterCol() {
  const cols = state.columns || [];
  filterCol.innerHTML = cols.map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`).join("");
  const groupDefault = cols.find((c) => c.name.toLowerCase().includes("group")) || cols[0];
  if (groupDefault) filterCol.value = groupDefault.name;
  state.filterCol = filterCol.value || null;
  resetFilterInputs();
}

function isDateColumn(name) {
  return /date|time|day|created|updated/i.test(name);
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function presetValue(preset) {
  const d = new Date();
  if (preset === "today") return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  if (preset === "yesterday") {
    const y = new Date();
    y.setDate(y.getDate() - 1);
    return `${y.getFullYear()}-${pad2(y.getMonth() + 1)}-${pad2(y.getDate())}`;
  }
  if (preset === "month") return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`;
  if (preset === "year") return `${d.getFullYear()}`;
  return "";
}

function resetFilterInputs() {
  state.filterVal = "";
  filterVal.value = "";
  filterDate.value = "";
  updateFilterInputMode();
}

function updateFilterInputMode() {
  const isDate = isDateColumn(state.filterCol || "");
  filterVal.classList.toggle("hidden", isDate);
  filterDate.classList.toggle("hidden", !isDate);
  filterPresets.classList.toggle("hidden", !isDate);
}

function reloadCurrent() {
  if (state.mode === "stats") loadStats();
  else loadData();
}

function filterQuery() {
  if (!state.filterCol || !state.filterVal) return "";
  return `&filter_col=${enc(state.filterCol)}&filter_val=${enc(state.filterVal)}`;
}

async function loadData() {
  const url = `/api/data?db=${enc(state.db)}&table=${enc(state.table)}&page=${state.page}&size=${state.size}${filterQuery()}`;
  const res = await fetch(url);
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const data = await res.json();
  state.total = data.total;

  emptyHint.classList.add("hidden");
  tableView.classList.remove("hidden");
  renderTable(data.columns, data.rows);
  renderPagination();
}

async function loadStats() {
  if (!state.groupFields.length || !state.sumField) {
    state.total = 0;
    emptyHint.classList.add("hidden");
    tableView.classList.remove("hidden");
    renderTable([], []);
    renderPagination();
    return;
  }
  const url = `/api/aggregate?db=${enc(state.db)}&table=${enc(state.table)}&group_by=${enc(state.groupFields.join(","))}&sum=${enc(state.sumField)}`;
  const res = await fetch(url);
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const data = await res.json();
  state.total = data.total;

  emptyHint.classList.add("hidden");
  tableView.classList.remove("hidden");
  renderTable(data.columns, data.rows);
  renderPagination();
}

function renderTable(columns, rows) {
  currentColumns = columns;
  const thead = dataTable.querySelector("thead");
  const tbody = dataTable.querySelector("tbody");
  const showCheck = state.mode === "data";

  thead.innerHTML = `<tr>
    ${columns.map((c, i) => showCheck
      ? `<th><label><input type="checkbox" class="col-check" data-index="${i}" checked><span class="col-label">${escapeHtml(c)}</span></label></th>`
      : `<th>${escapeHtml(c)}</th>`).join("")}
  </tr>`;

  tbody.innerHTML = rows.map((row) => `
    <tr>${row.map((cell) => `<td>${escapeHtml(cell == null ? "" : cell)}</td>`).join("")}</tr>
  `).join("");

  if (showCheck) {
    selectAll.checked = true;
    syncSelectAll();
  }
}

function syncSelectAll() {
  const checks = [...document.querySelectorAll(".col-check")];
  const checked = checks.filter((c) => c.checked).length;
  selectAll.checked = checks.length > 0 && checked === checks.length;
  selectAll.indeterminate = checked > 0 && checked < checks.length;
}

function renderPagination() {
  rowInfo.textContent = `当前表：${state.db} / ${state.table}`;
  if (state.mode === "stats") {
    prevBtn.style.display = "none";
    nextBtn.style.display = "none";
    pageInfo.textContent = `共 ${state.total} 行`;
    return;
  }
  prevBtn.style.display = "";
  nextBtn.style.display = "";
  const totalPages = Math.max(1, Math.ceil(state.total / state.size));
  pageInfo.textContent = `第 ${state.page} / ${totalPages} 页（共 ${state.total} 行）`;
  prevBtn.disabled = state.page <= 1;
  nextBtn.disabled = state.page >= totalPages;
}

function selectedColumns() {
  return [...document.querySelectorAll(".col-check")]
    .filter((c) => c.checked)
    .map((c) => c.getAttribute("data-index"))
    .map((i) => currentColumns[Number(i)]);
}

async function exportExcel() {
  let url;
  if (state.mode === "stats") {
    url = `/api/export?db=${enc(state.db)}&table=${enc(state.table)}&group_by=${enc(state.groupFields.join(","))}&sum=${enc(state.sumField)}`;
  } else {
    const fields = selectedColumns().join(",");
    url = `/api/export?db=${enc(state.db)}&table=${enc(state.table)}&fields=${enc(fields)}${filterQuery()}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${state.db}_${state.table}.xlsx`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setMode(mode) {
  state.mode = mode;
  modeDataBtn.classList.toggle("active", mode === "data");
  modeStatsBtn.classList.toggle("active", mode === "stats");
  selectAllWrap.classList.toggle("hidden", mode === "stats");
  filterBar.classList.toggle("hidden", mode === "stats");
  updateStatsControls();
  if (!state.table) return;
  if (mode === "stats") {
    loadStats();
  } else {
    loadData();
  }
}

selectAll.addEventListener("change", () => {
  document.querySelectorAll(".col-check").forEach((c) => (c.checked = selectAll.checked));
  syncSelectAll();
});

dataTable.addEventListener("change", (e) => {
  if (e.target.classList.contains("col-check")) syncSelectAll();
});

exportBtn.addEventListener("click", exportExcel);
modeDataBtn.addEventListener("click", () => setMode("data"));
modeStatsBtn.addEventListener("click", () => setMode("stats"));

filterApply.addEventListener("click", () => {
  state.filterCol = filterCol.value || null;
  state.filterVal = filterVal.value.trim();
  state.page = 1;
  reloadCurrent();
});

filterClear.addEventListener("click", () => {
  resetFilterInputs();
  state.page = 1;
  reloadCurrent();
});

filterCol.addEventListener("change", () => {
  state.filterCol = filterCol.value || null;
  resetFilterInputs();
});

filterDate.addEventListener("change", () => {
  state.filterVal = filterDate.value;
  state.page = 1;
  reloadCurrent();
});

filterPresets.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-preset]");
  if (!btn) return;
  state.filterVal = presetValue(btn.dataset.preset);
  state.page = 1;
  reloadCurrent();
});

groupAddBtn.addEventListener("click", () => {
  const v = groupAddCol.value;
  if (v && !state.groupFields.includes(v)) {
    state.groupFields.push(v);
    renderGroupFields();
    loadStats();
  }
});

groupFields.addEventListener("click", (e) => {
  const btn = e.target.closest(".gf-remove");
  if (!btn) return;
  state.groupFields = state.groupFields.filter((f) => f !== btn.dataset.field);
  renderGroupFields();
  loadStats();
});

sumCol.addEventListener("change", () => {
  state.sumField = sumCol.value || null;
  loadStats();
});

prevBtn.addEventListener("click", () => {
  if (state.page > 1) {
    state.page--;
    loadData();
  }
});

nextBtn.addEventListener("click", () => {
  state.page++;
  loadData();
});

loadDatabases();
