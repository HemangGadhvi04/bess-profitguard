const state = {
  dataDir: "data",
  dispatchRevenue: 7500,
  sessionId: "",
};

const uploadInputs = {
  bess_telemetry: "uploadBessTelemetry",
  site_load: "uploadSiteLoad",
  pv_generation: "uploadPvGeneration",
  tariff: "uploadTariff",
  ev_sessions: "uploadEvSessions",
  battery_config: "uploadBatteryConfig",
};

const money = (value) => `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const number = (value, suffix = "") => value === null || value === undefined ? "n/a" : `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;

const el = (id) => document.getElementById(id);
const cssColor = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function setMessage(text, isError = false) {
  const box = el("message");
  box.hidden = !text;
  box.textContent = text || "";
  box.classList.toggle("error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return response.json();
}

async function checkStatus() {
  try {
    const result = await api("/api/status");
    el("apiStatus").textContent = result.status === "ok" ? "API online" : "API issue";
    el("apiStatus").className = "status-pill ok";
  } catch (error) {
    el("apiStatus").textContent = "API offline";
    el("apiStatus").className = "status-pill bad";
  }
}

function readControls() {
  state.dataDir = el("dataDir").value.trim() || "data";
  state.dispatchRevenue = Number(el("dispatchRevenue").value || 0);
  const params = new URLSearchParams({ data_dir: state.dataDir, dispatch_revenue: String(state.dispatchRevenue) });
  el("reportLink").href = `/api/report/html?${params.toString()}`;
}

async function generateSampleData() {
  readControls();
  setMessage("Generating sample data...");
  await api("/api/sample-data", {
    method: "POST",
    body: JSON.stringify({
      output_dir: state.dataDir,
      days: Number(el("sampleDays").value || 7),
      seed: Number(el("sampleSeed").value || 42),
    }),
  });
  setMessage(`Sample data generated in ${state.dataDir}. Running analysis...`);
  await runAnalysis();
}

async function createSession() {
  const baseDir = el("uploadBaseDir").value.trim() || "runs";
  setMessage("Creating upload session...");
  const result = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ base_dir: baseDir }),
  });
  state.sessionId = result.session_id;
  state.dataDir = result.data_dir;
  el("sessionId").value = result.session_id;
  el("dataDir").value = result.data_dir;
  readControls();
  await refreshSessionFiles();
  setMessage(`Upload session created. Data directory set to ${result.data_dir}.`);
}

async function uploadSelectedFiles() {
  if (!state.sessionId) {
    throw new Error("Create an upload session first.");
  }
  const baseDir = el("uploadBaseDir").value.trim() || "runs";
  const selected = Object.entries(uploadInputs).filter(([, inputId]) => el(inputId).files.length > 0);
  if (!selected.length) {
    throw new Error("Choose at least one CSV file to upload.");
  }
  setMessage(`Uploading ${selected.length} file(s)...`);
  for (const [fileType, inputId] of selected) {
    const formData = new FormData();
    formData.append("file_type", fileType);
    formData.append("base_dir", baseDir);
    formData.append("file", el(inputId).files[0]);
    const response = await fetch(`/api/sessions/${encodeURIComponent(state.sessionId)}/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Upload failed for ${fileType}: ${detail}`);
    }
  }
  await refreshSessionFiles();
  setMessage("Selected CSV files uploaded.");
}

async function refreshSessionFiles() {
  if (!state.sessionId) {
    el("uploadStatus").textContent = "No upload session yet.";
    return;
  }
  const baseDir = el("uploadBaseDir").value.trim() || "runs";
  const params = new URLSearchParams({ base_dir: baseDir });
  const result = await api(`/api/sessions/${encodeURIComponent(state.sessionId)}/files?${params.toString()}`);
  const uploaded = Object.keys(result.files).length;
  const missing = result.missing.length ? `Missing: ${result.missing.join(", ")}` : "All required files uploaded.";
  el("uploadStatus").textContent = `${uploaded}/6 files uploaded. ${missing}`;
  state.dataDir = result.data_dir;
  el("dataDir").value = result.data_dir;
  readControls();
}

function renderValidation(reports) {
  const rows = reports.map((report) => {
    const statusClass = report.passed ? "good" : "bad";
    const status = report.passed ? "PASS" : "FAIL";
    return `<tr>
      <td>${report.dataset}</td>
      <td class="${statusClass}">${status}</td>
      <td>${report.error_count}</td>
      <td>${report.warning_count}</td>
    </tr>`;
  }).join("");
  el("validationRows").innerHTML = rows;
  const passed = reports.every((report) => report.passed);
  const warnings = reports.reduce((sum, report) => sum + report.warning_count, 0);
  el("validationMetric").textContent = passed ? "PASS" : "FAIL";
  el("validationMetric").className = passed ? "good" : "bad";
  el("validationNote").textContent = `${warnings} warnings`;
}

function renderStrategies(dispatch) {
  const strategies = [dispatch.baseline, dispatch.energy_cost_only, dispatch.degradation_aware];
  el("strategyRows").innerHTML = strategies.map((strategy) => `<tr>
    <td>${strategy.strategy}</td>
    <td>${money(strategy.energy_cost)}</td>
    <td>${money(strategy.demand_charge_cost)}</td>
    <td>${money(strategy.gross_savings)}</td>
    <td>${money(strategy.degradation_cost)}</td>
    <td>${money(strategy.net_savings)}</td>
    <td>${number(strategy.ev_readiness_percent, "%")}</td>
    <td>${number(strategy.peak_grid_import_kw, " kW")}</td>
    <td>${number(strategy.total_discharge_energy_kwh, " kWh")}</td>
  </tr>`).join("");
}

function renderSchedule(dispatch) {
  el("scheduleRows").innerHTML = dispatch.schedule.slice(0, 12).map((item) => `<tr>
    <td>${item.timestamp}</td>
    <td>${number(item.charge_kw, " kW")}</td>
    <td>${number(item.discharge_kw, " kW")}</td>
    <td>${number(item.soc_percent, "%")}</td>
    <td>${number(item.grid_import_kw, " kW")}</td>
    <td>${money(item.energy_price_per_kwh)}/kWh</td>
  </tr>`).join("");
}

function renderRisks(health, degradation) {
  const reasons = [...(health.risk_reasons || []), ...(degradation.reasons || [])];
  el("riskReasons").innerHTML = reasons.length
    ? reasons.map((reason) => `<li>${reason}</li>`).join("")
    : "<li>No material risk reasons detected.</li>";
}

function clearCanvas(canvas, ctx, title) {
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = cssColor("--muted");
  ctx.font = "13px Arial";
  ctx.textAlign = "center";
  ctx.fillText(title, width / 2, height / 2);
}

function setupCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(320, Math.floor(rect.width * ratio));
  canvas.height = Math.floor(220 * ratio);
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  return { ctx, width: canvas.width / ratio, height: canvas.height / ratio };
}

function drawAxes(ctx, width, height, min, max, unit) {
  const pad = { left: 44, right: 12, top: 12, bottom: 28 };
  ctx.strokeStyle = cssColor("--line");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, height - pad.bottom);
  ctx.lineTo(width - pad.right, height - pad.bottom);
  ctx.stroke();

  ctx.fillStyle = cssColor("--muted");
  ctx.font = "11px Arial";
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(max)}${unit}`, pad.left - 7, pad.top + 4);
  ctx.fillText(`${Math.round(min)}${unit}`, pad.left - 7, height - pad.bottom + 4);
  return pad;
}

function drawLineChart(canvasId, values, { min = null, max = null, unit = "", color = cssColor("--accent") } = {}) {
  const canvas = el(canvasId);
  const { ctx, width, height } = setupCanvas(canvas);
  if (!values.length) {
    clearCanvas(canvas, ctx, "Run analysis to draw chart");
    return;
  }
  const actualMin = min === null ? Math.min(...values) : min;
  const actualMax = max === null ? Math.max(...values) : max;
  const range = actualMax - actualMin || 1;
  const pad = drawAxes(ctx, width, height, actualMin, actualMax, unit);
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((value, index) => {
    const x = pad.left + (index / Math.max(1, values.length - 1)) * chartWidth;
    const y = pad.top + (1 - ((value - actualMin) / range)) * chartHeight;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawBarChart(canvasId, series, { unit = "", positiveColor = cssColor("--accent"), negativeColor = cssColor("--warn") } = {}) {
  const canvas = el(canvasId);
  const { ctx, width, height } = setupCanvas(canvas);
  if (!series.length) {
    clearCanvas(canvas, ctx, "Run analysis to draw chart");
    return;
  }
  const values = series.flatMap((item) => Array.isArray(item) ? item : [item]);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const pad = drawAxes(ctx, width, height, -maxAbs, maxAbs, unit);
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const zeroY = pad.top + chartHeight / 2;
  const barSlot = chartWidth / series.length;

  ctx.strokeStyle = cssColor("--line");
  ctx.beginPath();
  ctx.moveTo(pad.left, zeroY);
  ctx.lineTo(width - pad.right, zeroY);
  ctx.stroke();

  series.forEach((item, index) => {
    const pair = Array.isArray(item) ? item : [item];
    pair.forEach((value, pairIndex) => {
      const barWidth = Math.max(3, barSlot / (pair.length + 1));
      const x = pad.left + index * barSlot + pairIndex * barWidth + 2;
      const barHeight = Math.abs(value) / maxAbs * (chartHeight / 2);
      const y = value >= 0 ? zeroY - barHeight : zeroY;
      ctx.fillStyle = value >= 0 ? positiveColor : negativeColor;
      ctx.fillRect(x, y, barWidth - 2, barHeight);
    });
  });
}

function renderCharts(dispatch) {
  const schedule = dispatch.schedule || [];
  drawLineChart("socChart", schedule.map((item) => Number(item.soc_percent)), { min: 0, max: 100, unit: "%", color: cssColor("--good") });
  drawBarChart(
    "powerChart",
    schedule.map((item) => [Number(item.discharge_kw), -Number(item.charge_kw)]),
    { unit: " kW", positiveColor: cssColor("--accent"), negativeColor: cssColor("--warn") },
  );
  drawBarChart("gridChart", schedule.map((item) => Number(item.grid_import_kw)), { unit: " kW", positiveColor: cssColor("--accent") });
}

async function runAnalysis() {
  readControls();
  setMessage("Running validation, health, degradation, and dispatch analysis...");
  const validation = await api(`/api/validation?data_dir=${encodeURIComponent(state.dataDir)}`);
  const health = await api(`/api/battery-health?data_dir=${encodeURIComponent(state.dataDir)}`);
  const degradation = await api("/api/degradation-cost", {
    method: "POST",
    body: JSON.stringify({ data_dir: state.dataDir, dispatch_revenue: state.dispatchRevenue }),
  });
  const dispatch = await api("/api/dispatch", {
    method: "POST",
    body: JSON.stringify({ data_dir: state.dataDir, dispatch_revenue: state.dispatchRevenue }),
  });

  renderValidation(validation.reports);
  renderStrategies(dispatch);
  renderSchedule(dispatch);
  renderRisks(health, degradation);
  renderCharts(dispatch);

  el("riskMetric").textContent = String(health.risk_level || "--").toUpperCase();
  el("riskMetric").className = health.risk_level === "high" ? "bad" : health.risk_level === "medium" ? "warn" : "good";
  el("riskNote").textContent = `Stress score ${number(health.stress_score)}/100`;
  el("sohMetric").textContent = number(health.estimated_soh_percent, "%");
  el("degradationMetric").textContent = money(degradation.estimated_degradation_cost);
  el("netSavingsMetric").textContent = money(dispatch.degradation_aware.net_savings);
  el("recommendationMetric").textContent = dispatch.degradation_aware.net_savings >= dispatch.energy_cost_only.net_savings ? "Degradation-aware" : "Cost-only";

  setMessage(dispatch.recommendation);
}

el("generateBtn").addEventListener("click", () => generateSampleData().catch((error) => setMessage(error.message, true)));
el("runBtn").addEventListener("click", () => runAnalysis().catch((error) => setMessage(error.message, true)));
el("createSessionBtn").addEventListener("click", () => createSession().catch((error) => setMessage(error.message, true)));
el("uploadFilesBtn").addEventListener("click", () => uploadSelectedFiles().catch((error) => setMessage(error.message, true)));
el("refreshFilesBtn").addEventListener("click", () => refreshSessionFiles().catch((error) => setMessage(error.message, true)));
["dataDir", "dispatchRevenue"].forEach((id) => el(id).addEventListener("input", readControls));

readControls();
checkStatus();
