(() => {
  "use strict";

  const API_ROOT = "/api/scenarios";
  const numberFields = new Set([
    "model_size_billion", "training_runs_per_month", "monthly_requests_million",
    "average_demand_units", "peak_demand_units", "annual_growth_pct",
    "productivity_value_per_hour", "downtime_hours_monthly", "accelerator_count",
    "compute_hourly_cost", "productive_utilization_pct", "storage_tb",
    "storage_per_tb_month", "network_egress_tb_month", "network_per_gb", "power_kw",
    "pue", "power_per_kwh", "staff_fte", "staff_annual_cost", "operating_hours_year",
  ]);
  const defaultAssumptions = [
    { assumption: "Accelerator pricing", value: "$3.35 / hour", source: "Fictional vendor estimate · validate", confidence: "medium" },
    { assumption: "Demand growth", value: "18% annually", source: "Illustrative planning hypothesis", confidence: "low" },
    { assumption: "Staffing model", value: "3.0 FTE", source: "Fictional operating model", confidence: "medium" },
  ];
  const SOURCE_METADATA = " | workbench-meta:";
  let state = {
    scenarios: [], activeId: null, dirty: false, loading: true, saving: false,
    assumptions: defaultAssumptions, query: "", authoritativeResult: null, previewingSensitivity: false,
    sensitivity: { growth: 18, utilization: 68, price: 100 },
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const setState = (patch) => { state = { ...state, ...patch }; };
  const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  const money = (value, digits = 0) => new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: digits,
  }).format(Number.isFinite(value) ? value : 0);
  const percent = (value) => `${Number(value).toFixed(1).replace(".0", "")}%`;
  const roundMoney = (value) => Math.round((value + Number.EPSILON) * 100) / 100;
  const roundPayback = (value) => Math.round((value + Number.EPSILON) * 10) / 10;
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  async function api(path = "", options = {}) {
    const response = await fetch(`${API_ROOT}${path}`, {
      headers: { "Content-Type": "application/json", Accept: "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (response.status === 204) return null;
    let body;
    try { body = await response.json(); } catch (_) { throw new Error("The service returned an unreadable response."); }
    if (!response.ok || body?.success === false) {
      const detail = body?.error?.message || body?.detail || body?.message;
      throw new Error(publicError(response.status, detail));
    }
    if (body?.success !== undefined && body.success !== true) throw new Error("The service returned an invalid response.");
    return body;
  }

  function publicError(status, detail) {
    const safe = typeof detail === "string" && detail.length <= 180 && !/[\r\n<>]|traceback|stack/i.test(detail);
    if (safe) return detail;
    if (status === 404) return "That scenario is no longer available.";
    if (status === 422) return "Review the scenario inputs and try again.";
    return status >= 500 ? "The workbench service could not complete the request." : "The request could not be completed.";
  }

  function normalizeList(body) {
    if (Array.isArray(body)) return body;
    if (Array.isArray(body?.items)) return body.items;
    if (Array.isArray(body?.scenarios)) return body.scenarios;
    if (Array.isArray(body?.data)) return body.data;
    return [];
  }

  function normalizeScenario(body) {
    const candidate = body?.scenario || body?.data || body || {};
    const analysis = candidate.scenario && !candidate.input ? candidate.scenario : candidate;
    if (!analysis.input) return analysis;
    return { ...analysis.input, id: analysis.scenario_id, run_id: analysis.run_id, version: analysis.version, created_at: analysis.created_at, result: analysis.result };
  }

  function scenarioId(scenario) {
    return scenario?.id ?? scenario?.scenario_id ?? scenario?.uuid ?? null;
  }

  function scenarioMeta(scenario) {
    const updated = scenario.updated_at || scenario.created_at;
    const comparison = scenario.comparison_type || scenario.input?.comparison_type;
    if (!updated) return comparison?.replaceAll("_", " ") || "Working hypothesis";
    const date = new Date(updated);
    return Number.isNaN(date.valueOf()) ? "Working hypothesis" : `Updated ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
  }

  async function loadScenarios() {
    setState({ loading: true });
    showScenarioState("loading");
    try {
      const scenarios = normalizeList(await api());
      setState({ scenarios, loading: false });
      renderScenarioList();
      showScenarioState(scenarios.length ? "ready" : "empty");
      if (!state.activeId && scenarios.length) await selectScenario(scenarioId(scenarios[0]), true);
    } catch (error) {
      setState({ loading: false });
      setText("#scenario-error-message", error.message);
      showScenarioState("error");
    }
  }

  function showScenarioState(mode) {
    $("#scenario-loading").hidden = mode !== "loading";
    $("#scenario-error").hidden = mode !== "error";
    $("#scenario-empty").hidden = mode !== "empty";
    $("#scenario-list").hidden = mode !== "ready";
  }

  function renderScenarioList() {
    const list = $("#scenario-list");
    list.replaceChildren();
    const query = state.query.trim().toLowerCase();
    const filtered = state.scenarios.filter((item) => (item.name || item.input?.name || "Untitled scenario").toLowerCase().includes(query));
    filtered.forEach((scenario) => list.append(createScenarioButton(scenario)));
    if (!filtered.length && state.scenarios.length) list.append(el("p", "scenario-no-match", "No matching scenarios."));
  }

  function createScenarioButton(scenario) {
    const id = scenarioId(scenario);
    const button = el("button", "scenario-item");
    button.type = "button";
    button.dataset.id = String(id);
    button.setAttribute("aria-current", id === state.activeId ? "page" : "false");
    const name = scenario.name || scenario.input?.name || "Untitled scenario";
    const mark = el("span", "scenario-mark", name.trim().charAt(0).toUpperCase());
    const copy = el("span", "scenario-item-copy");
    copy.append(el("strong", "", name), el("small", "", scenarioMeta(scenario)));
    button.append(mark, copy);
    button.addEventListener("click", () => selectScenario(id));
    return button;
  }

  async function selectScenario(id, bypassGuard = false) {
    if (!id || id === state.activeId) return;
    if (!bypassGuard && state.dirty && !(await confirmAction("Discard unsaved changes?", "Switching scenarios will discard the current draft.", "Discard changes"))) return;
    setWorkspaceBusy(true);
    try {
      const scenario = normalizeScenario(await api(`/${encodeURIComponent(id)}`));
      setState({ activeId: id, dirty: false });
      applyScenario(scenario);
      renderScenarioList();
      updateSyncState();
    } catch (error) { toast(error.message, "error"); }
    finally { setWorkspaceBusy(false); }
  }

  function applyScenario(scenario) {
    const form = $("#scenario-form");
    $$('[name]', form).forEach((control) => {
      if (control.name === "horizon") return;
      const path = control.name.startsWith("current.") ? control.name.replace("current.", "current_infrastructure.")
        : control.name.startsWith("proposed.") ? control.name.replace("proposed.", "proposed_infrastructure.") : control.name;
      const value = path.split(".").reduce((item, key) => item?.[key], scenario);
      if (value !== undefined && value !== null) control.value = String(value);
    });
    const assumptions = normalizeAssumptions(scenario.assumption_sources);
    const sensitivity = { growth: Number(scenario.workload?.annual_growth_pct ?? 18), utilization: Number(scenario.proposed_infrastructure?.productive_utilization_pct ?? 68), price: 100 };
    setState({ assumptions, authoritativeResult: scenario.result || null, previewingSensitivity: false, sensitivity });
    syncSensitivityControls();
    setText("#scenario-title", scenario.name || "Untitled infrastructure decision");
    setText("#updated-label", scenarioMeta(scenario));
    $("#delete-scenario").hidden = !scenarioId(scenario);
    renderAssumptions();
    renderAnalysis();
  }

  function normalizeAssumption(item) {
    if (typeof item === "string") return { assumption: "Source", ...splitStoredSource(item) };
    const stored = splitStoredSource(item.source || item.evidence || item.url || "");
    return {
      assumption: item.assumption || item.name || item.input || "Assumption",
      value: item.value === undefined ? stored.value : String(item.value),
      source: stored.source,
      confidence: item.confidence || stored.confidence,
    };
  }

  function splitStoredSource(value) {
    const markerIndex = value.lastIndexOf(SOURCE_METADATA);
    if (markerIndex < 0) return { source: value, value: "", confidence: "medium" };
    try {
      const metadata = JSON.parse(decodeURIComponent(value.slice(markerIndex + SOURCE_METADATA.length)));
      return { source: value.slice(0, markerIndex), value: String(metadata.value || ""), confidence: metadata.confidence || "medium" };
    } catch (_) { return { source: value, value: "", confidence: "medium" }; }
  }

  function serializeAssumption(item) {
    const metadata = encodeURIComponent(JSON.stringify({ value: item.value, confidence: item.confidence }));
    const source = item.source.trim() || "Unverified hypothesis";
    return `${source.slice(0, Math.max(0, 500 - SOURCE_METADATA.length - metadata.length))}${SOURCE_METADATA}${metadata}`;
  }

  function assumptionSources(items) {
    return items.reduce((sources, item, index) => {
      const base = (item.assumption.trim() || `Assumption ${index + 1}`).slice(0, 120);
      const key = sources[base] === undefined ? base : `${base.slice(0, 112)} (${index + 1})`;
      return { ...sources, [key]: serializeAssumption(item) };
    }, {});
  }

  function normalizeAssumptions(sources) {
    if (Array.isArray(sources)) return sources.map(normalizeAssumption);
    if (sources && typeof sources === "object") return Object.entries(sources).map(([assumption, source]) => normalizeAssumption({ assumption, source }));
    return defaultAssumptions.map((item) => ({ ...item }));
  }

  function formValue(name) {
    const input = $(`[name="${name}"]`, $("#scenario-form"));
    if (!input) return "";
    const key = name.split(".").at(-1);
    return numberFields.has(key) || ["migration_cost", "implementation_cost", "contract_years"].includes(key) ? Number(input.value) : input.value.trim();
  }

  function infrastructure(prefix) {
    return {
      label: formValue(`${prefix}.label`), infrastructure_type: formValue(`${prefix}.infrastructure_type`),
      accelerator_count: formValue(`${prefix}.accelerator_count`), compute_hourly_cost: formValue(`${prefix}.compute_hourly_cost`),
      productive_utilization_pct: formValue(`${prefix}.productive_utilization_pct`), storage_tb: formValue(`${prefix}.storage_tb`),
      storage_per_tb_month: formValue(`${prefix}.storage_per_tb_month`), network_egress_tb_month: formValue(`${prefix}.network_egress_tb_month`),
      network_per_gb: formValue(`${prefix}.network_per_gb`), power_kw: formValue(`${prefix}.power_kw`), pue: formValue(`${prefix}.pue`),
      power_per_kwh: formValue(`${prefix}.power_per_kwh`), staff_fte: formValue(`${prefix}.staff_fte`),
      staff_annual_cost: formValue(`${prefix}.staff_annual_cost`), operating_hours_year: formValue(`${prefix}.operating_hours_year`),
    };
  }

  function workload() {
    return {
      workload_type: formValue("workload.workload_type"), model_size_billion: formValue("workload.model_size_billion"),
      training_runs_per_month: formValue("workload.training_runs_per_month"), monthly_requests_million: formValue("workload.monthly_requests_million"),
      average_demand_units: formValue("workload.average_demand_units"), peak_demand_units: formValue("workload.peak_demand_units"),
      annual_growth_pct: formValue("workload.annual_growth_pct"), productivity_value_per_hour: formValue("workload.productivity_value_per_hour"),
      downtime_hours_monthly: formValue("workload.downtime_hours_monthly"),
    };
  }

  function buildPayload() {
    return {
      name: formValue("name"), description: formValue("description"), fictional: true,
      comparison_type: formValue("comparison_type"), workload: workload(), current_infrastructure: infrastructure("current"),
      proposed_infrastructure: infrastructure("proposed"), migration_cost: formValue("migration_cost"),
      implementation_cost: formValue("implementation_cost"), contract_years: formValue("contract_years"),
      assumption_sources: assumptionSources(state.assumptions),
    };
  }

  async function saveScenario(event) {
    event.preventDefault();
    const form = $("#scenario-form");
    if (!form.reportValidity()) return;
    setState({ saving: true });
    updateSyncState();
    const path = state.activeId ? `/${encodeURIComponent(state.activeId)}` : "";
    const body = JSON.stringify(buildPayload());
    const options = state.activeId ? { method: "PUT", body } : { method: "POST", body };
    try {
      const saved = normalizeScenario(await api(path, options));
      const id = scenarioId(saved) || state.activeId;
      setState({ activeId: id, dirty: false, saving: false });
      applyScenario({ ...buildPayload(), ...saved, id });
      toast("Scenario saved", "success");
      await loadScenarios();
    } catch (error) {
      setState({ saving: false });
      updateSyncState();
      toast(error.message, "error");
    }
  }

  async function deleteScenario() {
    if (!state.activeId) return;
    const confirmed = await confirmAction("Delete this scenario?", "This removes the saved scenario and cannot be undone.", "Delete scenario");
    if (!confirmed) return;
    try {
      await api(`/${encodeURIComponent(state.activeId)}`, { method: "DELETE" });
      resetDraft();
      toast("Scenario deleted", "success");
      await loadScenarios();
    } catch (error) { toast(error.message, "error"); }
  }

  async function newScenario() {
    if (state.dirty && !(await confirmAction("Start a new scenario?", "Your unsaved draft will be discarded.", "Start new"))) return;
    resetDraft();
    $("#scenario-name").focus();
  }

  function resetDraft() {
    $("#scenario-form").reset();
    setState({ activeId: null, dirty: false, authoritativeResult: null, previewingSensitivity: false,
      assumptions: defaultAssumptions.map((item) => ({ ...item })), sensitivity: { growth: 18, utilization: 68, price: 100 } });
    setText("#scenario-title", "Untitled infrastructure decision");
    setText("#updated-label", "Not yet saved");
    $("#delete-scenario").hidden = true;
    renderScenarioList();
    renderAssumptions();
    renderAnalysis();
    updateSyncState();
  }

  function markDirty() {
    if (!state.dirty) setState({ dirty: true });
    setState({ previewingSensitivity: false });
    setText("#scenario-title", formValue("name") || "Untitled infrastructure decision");
    updateSyncState();
    renderAnalysis();
  }

  function updateSyncState() {
    const button = $("#save-button");
    button.disabled = state.saving;
    button.textContent = state.saving ? "Saving…" : "Save scenario";
    setText("#sync-label", state.saving ? "Saving draft" : state.dirty ? "Unsaved changes" : "Draft synced");
    $("#sync-state").classList.toggle("is-dirty", state.dirty);
  }

  function setWorkspaceBusy(busy) {
    $("#analysis").setAttribute("aria-busy", String(busy));
    $("#scenario-form").classList.toggle("is-loading", busy);
  }

  function renderAssumptions() {
    const body = $("#assumption-rows");
    body.replaceChildren();
    state.assumptions.forEach((assumption, index) => body.append(createAssumptionRow(assumption, index)));
    if (!state.assumptions.length) {
      const cell = el("td", "empty-cell", "No provenance recorded. Add a source before relying on the model.");
      cell.colSpan = 5;
      const row = el("tr"); row.append(cell); body.append(row);
    }
    updateConfidence();
  }

  function assumptionInput(value, label, key, index) {
    const input = el("input", "table-input");
    input.value = value;
    input.maxLength = key === "assumption" ? 120 : key === "value" ? 80 : 240;
    input.setAttribute("aria-label", `${label}, row ${index + 1}`);
    input.addEventListener("input", () => updateAssumption(index, key, input.value));
    return input;
  }

  function createAssumptionRow(item, index) {
    const row = el("tr");
    ["assumption", "value", "source"].forEach((key) => {
      const cell = el("td"); cell.append(assumptionInput(item[key], key, key, index)); row.append(cell);
    });
    const confidenceCell = el("td");
    const select = el("select", "confidence-select");
    select.setAttribute("aria-label", `Confidence, row ${index + 1}`);
    ["low", "medium", "high"].forEach((value) => { const option = el("option", "", value); option.value = value; option.selected = value === item.confidence; select.append(option); });
    select.addEventListener("change", () => updateAssumption(index, "confidence", select.value));
    confidenceCell.append(select);
    const actionCell = el("td");
    const remove = el("button", "row-action", "×"); remove.type = "button"; remove.setAttribute("aria-label", `Remove ${item.assumption || "assumption"}`);
    remove.addEventListener("click", () => removeAssumption(index)); actionCell.append(remove);
    row.append(confidenceCell, actionCell);
    return row;
  }

  function updateAssumption(index, key, value) {
    const assumptions = state.assumptions.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item);
    setState({ assumptions, dirty: true });
    updateSyncState();
    updateConfidence();
    renderAnalysis();
  }

  function addAssumption() {
    setState({ assumptions: [...state.assumptions, { assumption: "", value: "", source: "", confidence: "low" }], dirty: true });
    renderAssumptions();
    updateSyncState();
    renderAnalysis();
    const inputs = $$("#assumption-rows input"); inputs.at(-3)?.focus();
  }

  function removeAssumption(index) {
    setState({ assumptions: state.assumptions.filter((_, itemIndex) => itemIndex !== index), dirty: true });
    renderAssumptions();
    updateSyncState();
    renderAnalysis();
  }

  function annualCost(model, growthFactor = 1, capacityMultiplier = 1) {
    const compute = model.accelerator_count * model.compute_hourly_cost * model.operating_hours_year * growthFactor * capacityMultiplier;
    const storage = model.storage_tb * model.storage_per_tb_month * 12 * growthFactor;
    const network = model.network_egress_tb_month * 1000 * model.network_per_gb * 12 * growthFactor;
    const energy = model.power_kw * model.pue * model.power_per_kwh * model.operating_hours_year * growthFactor * capacityMultiplier;
    const staffing = model.staff_fte * model.staff_annual_cost;
    return roundMoney([compute, storage, network, energy, staffing].map(roundMoney).reduce((sum, value) => sum + value, 0));
  }

  function stateProjection(infrastructureModel, growthPct, transition = 0, capacityMultiplier = 1) {
    const recurring = [1, 2, 3, 4, 5].map((year) => annualCost(infrastructureModel, (1 + growthPct / 100) ** (year - 1), capacityMultiplier));
    const totals = recurring.map((value, index) => roundMoney(value + (index === 0 ? transition : 0)));
    return { recurring, cumulative: totals.map((_, index) => roundMoney(totals.slice(0, index + 1).reduce((sum, value) => sum + value, 0))) };
  }

  function unitEconomics(projection, workloadModel, infrastructureModel, years) {
    const growth = 1 + workloadModel.annual_growth_pct / 100;
    const factors = Array.from({ length: years }, (_, index) => growth ** index).reduce((sum, value) => sum + value, 0);
    const recurringCost = projection.recurring.slice(0, years).reduce((sum, value) => sum + value, 0);
    const trainingRuns = workloadModel.training_runs_per_month * 12 * factors;
    const requests = workloadModel.monthly_requests_million * 12 * factors;
    const productiveHours = infrastructureModel.accelerator_count * infrastructureModel.operating_hours_year * infrastructureModel.productive_utilization_pct / 100 * years;
    return { recurring_cost: roundMoney(recurringCost), cost_per_training_run: safeDivide(recurringCost, trainingRuns),
      cost_per_million_requests: safeDivide(recurringCost, requests), cost_per_productive_accelerator_hour: safeDivide(recurringCost, productiveHours) };
  }

  function safeDivide(numerator, denominator) { return denominator > 0 ? roundMoney(numerator / denominator) : null; }

  function calculatePayback(current, proposed, productivity, investment) {
    let remaining = investment;
    let months = 0;
    for (let index = 0; index < 5; index += 1) {
      const benefit = current.recurring[index] - proposed.recurring[index] + productivity[index];
      if (benefit > 0 && benefit >= remaining) return roundPayback(months + (remaining / benefit) * 12);
      remaining -= benefit;
      months += 12;
    }
    return null;
  }

  function calculateDraftModel() {
    const payload = buildPayload();
    const growthPct = state.previewingSensitivity ? state.sensitivity.growth : payload.workload.annual_growth_pct;
    const current = stateProjection(payload.current_infrastructure, growthPct);
    const proposedInfra = { ...payload.proposed_infrastructure, compute_hourly_cost: payload.proposed_infrastructure.compute_hourly_cost * state.sensitivity.price / 100 };
    const capacity = payload.proposed_infrastructure.productive_utilization_pct / state.sensitivity.utilization;
    const upfront = payload.migration_cost + payload.implementation_cost;
    const proposed = stateProjection(proposedInfra, growthPct, upfront, state.previewingSensitivity ? capacity : 1);
    const productivity = [1, 2, 3, 4, 5].map((year) => roundMoney(payload.workload.productivity_value_per_hour * payload.workload.downtime_hours_monthly * 12 * ((1 + growthPct / 100) ** (year - 1))));
    const payback = calculatePayback(current, proposed, productivity, upfront);
    const savings = current.cumulative.map((value, index) => roundMoney(value - proposed.cumulative[index]));
    const net = savings.map((value, index) => roundMoney(value + productivity.slice(0, index + 1).reduce((sum, item) => sum + item, 0)));
    return draftModel(payload, current, proposed, upfront, payback, net);
  }

  function draftModel(payload, current, proposed, upfront, payback, net) {
    return { payload, currentAnnual: current.recurring[0], proposedAnnual: proposed.recurring[0], upfront,
      currentTco: current.cumulative, proposedTco: proposed.cumulative, annualSavings: current.recurring[0] - proposed.recurring[0],
      payback, net3: net[2], net5: net[4], currentUnits: { 3: unitEconomics(current, payload.workload, payload.current_infrastructure, 3), 5: unitEconomics(current, payload.workload, payload.current_infrastructure, 5) },
      proposedUnits: { 3: unitEconomics(proposed, payload.workload, payload.proposed_infrastructure, 3), 5: unitEconomics(proposed, payload.workload, payload.proposed_infrastructure, 5) },
      confidence: draftConfidence(payload), authoritative: false };
  }

  function draftConfidence(payload) {
    const sources = payload.assumption_sources;
    const workloadPaths = Object.entries(payload.workload).filter(([key, value]) => key !== "workload_type" && value !== 0).map(([key]) => `workload.${key}`);
    const infrastructurePaths = ["current_infrastructure", "proposed_infrastructure"].flatMap((prefix) => Object.entries(payload[prefix]).filter(([, value]) => typeof value === "number" && value !== 0).map(([key]) => `${prefix}.${key}`));
    const transitionPaths = ["migration_cost", "implementation_cost"].filter((key) => payload[key] !== 0);
    const material = [...workloadPaths, ...infrastructurePaths, ...transitionPaths, "contract_years"];
    const sourced = material.filter((path) => sources[path] || sources[path.split(".").at(-1)]).length;
    const coverage = material.length ? sourced / material.length * 100 : 0;
    const contractCoverage = Math.min(payload.contract_years / 5, 1) * 100;
    const score = roundPayback(coverage * 0.8 + contractCoverage * 0.2);
    return { score, level: score >= 80 ? "High" : score >= 50 ? "Medium" : "Low", sourced_assumptions: sourced, material_assumptions: material.length };
  }

  function authoritativeModel(result) {
    const currentCosts = result.current.annual_costs;
    const proposedCosts = result.proposed.annual_costs;
    const cumulativeTotals = (costs) => costs.map((_, index) => costs.slice(0, index + 1).reduce((sum, item) => sum + item.total, 0));
    return { payload: buildPayload(), currentAnnual: currentCosts[0].recurring_total, proposedAnnual: proposedCosts[0].recurring_total,
      upfront: proposedCosts[0].transition, currentTco: cumulativeTotals(currentCosts), proposedTco: cumulativeTotals(proposedCosts),
      annualSavings: currentCosts[0].recurring_total - proposedCosts[0].recurring_total, payback: result.comparison.payback_months,
      net3: result.comparison.net_value_3_year, net5: result.comparison.net_value_5_year,
      currentUnits: { 3: result.current.unit_economics_3_year, 5: result.current.unit_economics_5_year },
      proposedUnits: { 3: result.proposed.unit_economics_3_year, 5: result.proposed.unit_economics_5_year },
      sensitivities: result.sensitivities, confidence: result.confidence, lineage: result.lineage, summary: result.executive_summary, authoritative: true };
  }

  function renderAnalysis() {
    if (!$("#scenario-form").checkValidity()) { renderInvalidAnalysis(); return; }
    const useAuthoritative = state.authoritativeResult && !state.dirty && !state.previewingSensitivity;
    const model = useAuthoritative ? authoritativeModel(state.authoritativeResult) : calculateDraftModel();
    setText("#analysis-source-label", model.authoritative ? "Saved engine result" : "Draft preview");
    renderMetrics(model);
    renderTcoChart(model);
    renderUnitEconomics(model);
    renderTornado(model);
    renderLineage(model);
    renderSummary(model);
  }

  function renderInvalidAnalysis() {
    setText("#analysis-source-label", "Draft needs attention");
    ["#net-impact", "#payback-period", "#unit-economics", "#payback-ring-value", "#upfront-cost", "#run-rate-delta"].forEach((selector) => setText(selector, "—"));
    setText("#net-impact-context", "Complete valid inputs to refresh the preview");
    setText("#payback-narrative", "Resolve the highlighted input before relying on this analysis.");
    ["#tco-chart", "#chart-summary", "#unit-economics-table", "#tornado-chart", "#lineage-grid", "#summary-points"].forEach((selector) => $(selector).replaceChildren());
    setText("#summary-headline", "The draft contains an invalid or incomplete input.");
    setText("#decision-gate-label", "Resolve model inputs");
    setText("#decision-gate-detail", "Review the highlighted field, then reassess the indicative outputs.");
  }

  function renderMetrics(model) {
    const horizon = Number($("#horizon-select").value);
    const impact = horizon === 3 ? model.net3 : model.net5;
    const unit = model.proposedUnits[horizon].cost_per_million_requests;
    setText("#net-impact", money(impact));
    setText("#net-impact-label", `${horizon}-year net impact`);
    setText("#net-impact-context", impact >= 0 ? `Indicative net value over ${horizon} years` : `Indicative net cost over ${horizon} years`);
    setText("#payback-period", model.payback ? `${model.payback.toFixed(1)} mo` : "No payback");
    setText("#unit-economics", money(unit, 2));
    setText("#payback-ring-value", model.payback ? model.payback.toFixed(1) : "—");
    setText("#upfront-cost", money(model.upfront));
    setText("#run-rate-delta", money(model.annualSavings));
    setText("#payback-narrative", paybackNarrative(model.payback));
    const degrees = model.payback ? Math.min(360, (model.payback / 60) * 360) : 360;
    $("#payback-ring").style.setProperty("--payback-angle", `${degrees}deg`);
  }

  function paybackNarrative(payback) {
    if (!payback) return "The modeled run rate does not recover transition costs within the analysis horizon.";
    if (payback <= 24) return "The hypothesis recovers transition costs inside a two-year planning window.";
    if (payback <= 60) return "Recovery is modeled inside five years, subject to the stated evidence quality.";
    return "Recovery extends beyond five years and warrants a stronger strategic rationale.";
  }

  function renderTcoChart(model) {
    const chart = $("#tco-chart"); chart.replaceChildren();
    const max = Math.max(...model.currentTco, ...model.proposedTco, 1);
    [1, 2, 3, 4, 5].forEach((year, index) => chart.append(createYearGroup(year, model.currentTco[index], model.proposedTco[index], max)));
    const savings3 = model.currentTco[2] - model.proposedTco[2];
    const savings5 = model.currentTco[4] - model.proposedTco[4];
    const summary = $("#chart-summary"); summary.replaceChildren();
    summary.append(summaryMetric("3-year TCO delta", money(savings3)), summaryMetric("5-year TCO delta", money(savings5)));
  }

  function createYearGroup(year, current, proposed, max) {
    const group = el("div", "year-group");
    const bars = el("div", "bar-pair");
    bars.append(createBar("current", current, max), createBar("proposed", proposed, max));
    group.append(bars, el("span", "year-label", `Y${year}`));
    return group;
  }

  function createBar(kind, value, max) {
    const bar = el("div", `tco-bar ${kind}`);
    bar.style.height = `${Math.max(4, (value / max) * 100)}%`;
    bar.title = `${kind === "current" ? "Current" : "Proposed"}: ${money(value)}`;
    const valueLabel = el("span", "bar-value", money(value)); bar.append(valueLabel);
    return bar;
  }

  function summaryMetric(label, value) {
    const item = el("div"); item.append(el("span", "", label), el("strong", "", value)); return item;
  }

  function renderUnitEconomics(model) {
    const body = $("#unit-economics-table"); body.replaceChildren();
    const horizon = Number($("#horizon-select").value);
    const current = model.currentUnits[horizon];
    const proposed = model.proposedUnits[horizon];
    const rows = [
      [`${horizon}-year recurring cost`, current.recurring_cost, proposed.recurring_cost],
      ["Cost / training run", current.cost_per_training_run, proposed.cost_per_training_run],
      ["Cost / 1M requests", current.cost_per_million_requests, proposed.cost_per_million_requests],
      ["Cost / productive accelerator-hour", current.cost_per_productive_accelerator_hour, proposed.cost_per_productive_accelerator_hour],
    ];
    rows.forEach(([label, current, proposed], index) => body.append(unitRow(label, current, proposed, index > 0)));
  }

  function unitRow(label, current, proposed, precise) {
    const row = el("tr");
    const comparable = current !== null && proposed !== null && current !== 0;
    const variance = comparable ? ((proposed - current) / current) * 100 : null;
    const values = [label, current === null ? "N/A" : money(current, precise ? 2 : 0), proposed === null ? "N/A" : money(proposed, precise ? 2 : 0), variance === null ? "N/A" : `${variance > 0 ? "+" : ""}${percent(variance)}`];
    values.forEach((value, index) => {
      const cell = el(index ? "td" : "th", index === 3 ? (variance <= 0 ? "positive" : "negative") : "", value);
      if (!index) cell.scope = "row"; row.append(cell);
    });
    return row;
  }

  function renderTornado(model) {
    const chart = $("#tornado-chart"); chart.replaceChildren();
    const drivers = model.sensitivities ? authoritativeDrivers(model.sensitivities) : draftDrivers(model);
    const max = Math.max(...drivers.map(([, impact]) => impact), 1);
    drivers.forEach(([label, impact]) => chart.append(tornadoRow(label, impact, max)));
  }

  function authoritativeDrivers(sensitivities) {
    const dimensions = [...new Set(sensitivities.map((item) => item.dimension))];
    return dimensions.map((dimension) => {
      const cases = sensitivities.filter((item) => item.dimension === dimension);
      const values = cases.map((item) => item.net_value_5_year);
      return [dimension.charAt(0).toUpperCase() + dimension.slice(1), Math.max(...values) - Math.min(...values)];
    });
  }

  function draftDrivers(model) {
    const payload = model.payload;
    const infra = payload.proposed_infrastructure;
    const ranges = [
      ["Utilization", [Math.max(1, infra.productive_utilization_pct - 10), infra.productive_utilization_pct, Math.min(100, infra.productive_utilization_pct + 10)]],
      ["Price", [infra.compute_hourly_cost * 0.9, infra.compute_hourly_cost, infra.compute_hourly_cost * 1.1]],
      ["Growth", [Math.max(-100, payload.workload.annual_growth_pct - 5), payload.workload.annual_growth_pct, payload.workload.annual_growth_pct + 5]],
      ["Energy", [infra.power_per_kwh * 0.8, infra.power_per_kwh, infra.power_per_kwh * 1.2]],
    ];
    return ranges.map(([dimension, values]) => {
      const netValues = values.map((value) => sensitivityNetValue(payload, dimension.toLowerCase(), value));
      return [dimension, Math.max(...netValues) - Math.min(...netValues)];
    });
  }

  function sensitivityNetValue(payload, dimension, value) {
    const baseInfra = payload.proposed_infrastructure;
    const infra = dimension === "price" ? { ...baseInfra, compute_hourly_cost: value }
      : dimension === "energy" ? { ...baseInfra, power_per_kwh: value } : baseInfra;
    const growth = dimension === "growth" ? value : payload.workload.annual_growth_pct;
    const capacity = dimension === "utilization" ? baseInfra.productive_utilization_pct / value : 1;
    const transition = payload.migration_cost + payload.implementation_cost;
    const current = stateProjection(payload.current_infrastructure, growth);
    const proposed = stateProjection(infra, growth, transition, capacity);
    const savings = current.cumulative[4] - proposed.cumulative[4];
    const productivity = [1, 2, 3, 4, 5].map((year) => roundMoney(payload.workload.productivity_value_per_hour * payload.workload.downtime_hours_monthly * 12 * ((1 + growth / 100) ** (year - 1))));
    return roundMoney(savings + productivity.reduce((sum, item) => sum + item, 0));
  }

  function tornadoRow(label, impact, max) {
    const row = el("div", "tornado-row"); row.append(el("span", "tornado-label", label));
    const track = el("div", "tornado-track");
    const low = el("span", "tornado-low"); const high = el("span", "tornado-high");
    const width = `${Math.max(5, (impact / max) * 48)}%`; low.style.width = width; high.style.width = width;
    track.append(low, high); row.append(track, el("strong", "", money(impact))); return row;
  }

  function renderLineage(model) {
    const grid = $("#lineage-grid"); grid.replaceChildren();
    if (model.lineage) {
      const preferred = model.lineage.filter((item) => ["current.annual_costs[1].compute", "proposed.tco_5_year", "comparison.roi_5_year_pct", "executive_summary.net_value_5_year"].includes(item.output_path));
      const visible = preferred.length ? preferred : model.lineage.slice(0, 4);
      visible
        .forEach((item, index) => grid.append(lineageCard(String(index + 1).padStart(2, "0"), item.output_path, item.formula, formatDerived(item.derived_value))));
      if (!visible.length) grid.append(el("p", "empty-lineage", "No calculation lineage was returned for this saved analysis."));
      return;
    }
    const steps = [
      ["01", "Annual compute", "accelerators × operating hours × unit cost", money(model.payload.current_infrastructure.accelerator_count * model.payload.current_infrastructure.operating_hours_year * model.payload.current_infrastructure.compute_hourly_cost)],
      ["02", "Annual run rate", "compute + storage + network + power + people", money(model.currentAnnual)],
      ["03", "Proposed entry cost", "migration cost + implementation cost", money(model.upfront)],
      ["04", "Five-year impact", "current cumulative TCO − proposed cumulative TCO", money(model.currentTco[4] - model.proposedTco[4])],
    ];
    steps.forEach((step) => grid.append(lineageCard(...step)));
  }

  function formatDerived(value) {
    if (typeof value === "boolean") return value ? "True" : "False";
    return typeof value === "number" ? money(value, 2) : String(value ?? "—");
  }

  function lineageCard(index, title, formula, value) {
    const card = el("article", "lineage-card");
    card.append(el("span", "lineage-index", index), el("h3", "", title), el("code", "", formula), el("strong", "", value));
    return card;
  }

  function renderSummary(model) {
    const impact = model.summary?.net_value_5_year ?? model.net5;
    const direction = impact >= 0 ? "lower" : "higher";
    setText("#summary-headline", model.summary?.recommendation || `The proposed state models ${money(Math.abs(impact))} ${direction} five-year net impact than the current estate.`);
    const points = $("#summary-points"); points.replaceChildren();
    [
      `Five-year modeled net impact: ${money(impact)}; five-year TCO delta: ${money(model.currentTco[4] - model.proposedTco[4])}.`,
      model.payback ? `Simple payback hypothesis: ${model.payback.toFixed(1)} months.` : "No simple payback appears within the modeled case.",
      model.confidence ? `${model.confidence.sourced_assumptions} of ${model.confidence.material_assumptions} material assumptions are sourced (${model.confidence.level} confidence).` : `${state.assumptions.length} source references are currently recorded.`,
    ].forEach((copy) => points.append(el("li", "", copy)));
    const weakEvidence = model.confidence ? model.confidence.level !== "High" : state.assumptions.some((item) => item.confidence === "low" || !item.source.trim());
    setText("#decision-gate-label", weakEvidence ? "Validate critical assumptions" : "Prepare controlled validation");
    setText("#decision-gate-detail", weakEvidence ? "Resolve low-confidence or unsourced inputs before commercial commitment." : "Test the operating model with a time-boxed pilot and explicit success criteria.");
  }

  function updateConfidence() {
    if (state.authoritativeResult && !state.dirty && !state.previewingSensitivity) {
      setText("#confidence-score", `${Math.round(state.authoritativeResult.confidence.score)} / 100`);
      return;
    }
    setText("#confidence-score", `${Math.round(draftConfidence(buildPayload()).score)} / 100`);
  }

  function updateSensitivity(event) {
    const key = event.target.id.replace("sensitivity-", "");
    const sensitivity = { ...state.sensitivity, [key]: Number(event.target.value) };
    setState({ sensitivity, previewingSensitivity: true });
    setText(`#${event.target.id}-output`, `${event.target.value}%`);
    renderAnalysis();
  }

  function resetSensitivity() {
    const utilization = Number(formValue("proposed.productive_utilization_pct"));
    const growth = Number(formValue("workload.annual_growth_pct"));
    setState({ sensitivity: { growth, utilization, price: 100 }, previewingSensitivity: false });
    ["growth", "utilization", "price"].forEach((key) => { const input = $(`#sensitivity-${key}`); input.value = state.sensitivity[key]; setText(`#sensitivity-${key}-output`, `${state.sensitivity[key]}%`); });
    renderAnalysis();
  }

  function syncSensitivityControls() {
    ["growth", "utilization", "price"].forEach((key) => {
      const input = $(`#sensitivity-${key}`);
      if (!input) return;
      input.value = state.sensitivity[key];
      setText(`#sensitivity-${key}-output`, `${state.sensitivity[key]}%`);
    });
  }

  function toggleExport(event) {
    event.stopPropagation();
    const menu = $("#export-menu"); menu.hidden = !menu.hidden;
    $("#export-button").setAttribute("aria-expanded", String(!menu.hidden));
    if (!menu.hidden) $("[role='menuitem']", menu)?.focus();
  }

  function exportScenario(event) {
    event.preventDefault();
    const format = event.currentTarget.dataset.export;
    if (!state.activeId) { toast("Save the scenario before exporting.", "error"); return; }
    window.location.assign(exportPath(state.activeId, format));
    closeExportMenu();
  }

  function exportPath(id, format) {
    return `${API_ROOT}/${encodeURIComponent(id)}/exports/${encodeURIComponent(format)}`;
  }

  function closeExportMenu() {
    $("#export-menu").hidden = true;
    $("#export-button").setAttribute("aria-expanded", "false");
  }

  function confirmAction(title, message, confirmLabel) {
    const dialog = $("#confirm-dialog");
    setText("#confirm-title", title); setText("#confirm-message", message); setText("#confirm-action", confirmLabel);
    dialog.showModal();
    return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }));
  }

  function toast(message, kind = "info") {
    const region = $("#toast-region");
    const notice = el("div", `toast toast-${kind}`, message); region.replaceChildren(notice);
    window.setTimeout(() => { if (notice.isConnected) notice.remove(); }, 4500);
  }

  async function copySummary() {
    const copy = [$("#summary-headline").textContent, ...$$("#summary-points li").map((item) => `• ${item.textContent}`)].join("\n");
    try { await navigator.clipboard.writeText(copy); toast("Executive summary copied", "success"); }
    catch (_) { toast("Copy is unavailable in this browser.", "error"); }
  }

  function bindEvents() {
    $("#scenario-form").addEventListener("submit", saveScenario);
    $("#scenario-form").addEventListener("input", (event) => { if (event.target.type !== "range") markDirty(); });
    $("#new-scenario").addEventListener("click", newScenario);
    $("#delete-scenario").addEventListener("click", deleteScenario);
    $("#retry-scenarios").addEventListener("click", loadScenarios);
    $("#add-assumption").addEventListener("click", addAssumption);
    $("#scenario-search").addEventListener("input", (event) => { setState({ query: event.target.value }); renderScenarioList(); });
    $("#horizon-select").addEventListener("change", renderAnalysis);
    $$("[id^='sensitivity-'][type='range']").forEach((input) => input.addEventListener("input", updateSensitivity));
    $("#reset-sensitivity").addEventListener("click", resetSensitivity);
    $("#export-button").addEventListener("click", toggleExport);
    $$('[data-export]').forEach((link) => link.addEventListener("click", exportScenario));
    $("#copy-summary").addEventListener("click", copySummary);
    document.addEventListener("click", (event) => { if (!$("#export-menu").contains(event.target)) closeExportMenu(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeExportMenu(); });
    window.addEventListener("beforeunload", (event) => { if (state.dirty) { event.preventDefault(); event.returnValue = ""; } });
  }

  function initialize() {
    bindEvents();
    renderAssumptions();
    renderAnalysis();
    updateSyncState();
    loadScenarios();
  }

  const testInterface = Object.freeze({ normalizeScenario, publicError, annualCost, splitStoredSource, serializeAssumption, assumptionSources, exportPath });
  if (typeof module !== "undefined" && module.exports) module.exports = testInterface;
  if (typeof document !== "undefined") initialize();
})();
