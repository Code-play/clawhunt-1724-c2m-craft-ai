/* C2M craft prototype - vanilla front end, no build step, no CDN. */
"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const esc = (value) =>
  String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);

const state = {
  lang: "en",
  i18n: { en: {}, zh: {} },
  spec: null,
  industries: [],
  styles: [],
  concepts: [],
  orders: [],
  catalog: {},
  selectedOrder: null,
  referencePalette: [],
  lastConcepts: [],
};

// The model sidecar runs as its own process (see model-sidecar/README.md).
// It is optional: without it the prototype still works, only the AI render
// button reports that the sidecar is offline.
const SIDECAR_URL = "http://127.0.0.1:8413";

const VERDICT_CLASS = {
  manufacturable: "ok",
  conditionally_manufacturable: "warn",
  not_manufacturable: "bad",
  not_assessable: "info",
};

function t(key) {
  const dict = state.i18n[state.lang] || {};
  return dict[key] || key;
}

function toast(message, kind = "error") {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast ${kind === "ok" ? "ok" : ""}`;
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => node.classList.add("hidden"), 5200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await response.json();
  } catch (error) {
    throw new Error(`HTTP ${response.status}`);
  }
  if (!response.ok || !body || body.ok === false) {
    const detail = body && body.error ? body.error : { message: `HTTP ${response.status}` };
    const extra = (detail.details || [])
      .slice(0, 3)
      .map((item) => `${item.path}: ${item.message}`)
      .join(" | ");
    throw new Error(`${detail.message}${extra ? ` (${extra})` : ""}`);
  }
  return body.data;
}

/* -- previews ----------------------------------------------------------- */
function hexToRgb(hex) {
  const value = String(hex).replace("#", "");
  return [parseInt(value.slice(0, 2), 16), parseInt(value.slice(2, 4), 16), parseInt(value.slice(4, 6), 16)];
}

function rgba(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}

function motifLayers(motif, accent) {
  switch (motif) {
    case "fret":
      return `repeating-linear-gradient(90deg, ${rgba(accent, 0.5)} 0 3px, transparent 3px 14px), repeating-linear-gradient(0deg, ${rgba(accent, 0.5)} 0 3px, transparent 3px 14px)`;
    case "wave":
      return `repeating-radial-gradient(circle at 50% 120%, transparent 0 18px, ${rgba(accent, 0.55)} 18px 20px)`;
    case "granule":
      return `radial-gradient(${rgba(accent, 0.75)} 1.6px, transparent 1.8px) 0 0/10px 10px`;
    case "openwork":
      return `repeating-radial-gradient(circle at 50% 50%, transparent 0 9px, ${rgba(accent, 0.6)} 9px 11px)`;
    case "carved":
    case "relief":
      return `repeating-linear-gradient(45deg, ${rgba(accent, 0.45)} 0 2px, transparent 2px 9px)`;
    case "inlay":
      return `repeating-linear-gradient(115deg, ${rgba(accent, 0.6)} 0 6px, transparent 6px 16px)`;
    default:
      return `repeating-radial-gradient(circle at 50% 50%, transparent 0 12px, ${rgba(accent, 0.5)} 12px 13px)`;
  }
}

function previewStyle(concept) {
  const colors = (concept.palette || []).map((entry) => entry.hex);
  const base = colors[0] || "#2a2f36";
  const second = colors[1] || "#40474f";
  const third = colors[2] || "#e8e2d6";
  const angle = (concept.preview && concept.preview.gradient_angle_deg) || 90;
  const motif = (concept.preview && concept.preview.motif_style) || "interlace";
  return [
    `background-color:${base}`,
    `background-image:${motifLayers(motif, second)}, radial-gradient(circle at 32% 24%, ${rgba(third, 0.85)} 0 15%, transparent 16%), linear-gradient(${angle}deg, ${base} 0%, ${second} 60%, ${base} 100%)`,
    "background-blend-mode:normal,soft-light,normal",
  ].join(";");
}

function swatches(colors) {
  return `<div class="swatches">${colors
    .map((color) => `<span class="swatch" style="background:${esc(color)}" title="${esc(color)}"></span>`)
    .join("")}</div>`;
}

function conceptCard(concept) {
  const facts = concept.craft_facts || {};
  const topFacts = Object.keys(facts)
    .sort()
    .slice(0, 4)
    .map((name) => `<dt>${esc(name)}</dt><dd>${esc(facts[name])}</dd>`)
    .join("");
  const colors = (concept.palette || []).map((entry) => entry.hex);
  return `<article class="concept">
    <header><h4>${esc(concept.title[state.lang] || concept.title.en)}</h4><span class="id">${esc(concept.concept_id)}</span></header>
    <div class="preview" style="${previewStyle(concept)}"><span class="tag">${esc(concept.preview.motif_style)} / ${esc(concept.preview.texture)}</span></div>
    ${swatches(colors)}
    <div class="muted">${esc(concept.industry)} · ${esc(concept.form.category)} · ${esc(concept.form.variant)} · ${esc(concept.material.name)}</div>
    <dl class="facts">${topFacts}</dl>
    <div class="ai-shot" id="ai-${esc(concept.concept_id)}"></div>
    <div class="ai-copy" id="copy-${esc(concept.concept_id)}"></div>
    <div class="actions">
      <button data-action="ws-assess" data-concept="${esc(concept.concept_id)}">${esc(t("common.assess"))}</button>
      <button data-action="ws-series" data-concept="${esc(concept.concept_id)}">${esc(t("common.series"))}</button>
      <button data-action="ws-order" data-concept="${esc(concept.concept_id)}">${esc(t("common.order"))}</button>
      <button data-action="ws-render" data-concept="${esc(concept.concept_id)}">${esc(t("ws.render"))}</button>
      <button data-action="ws-copy" data-concept="${esc(concept.concept_id)}">${esc(t("ws.copy"))}</button>
    </div>
  </article>`;
}

/* -- AI render via the model sidecar ------------------------------------ */
function conceptPrompt(concept) {
  const palette = (concept.palette || []).slice(0, 4).map((entry) => entry.hex).join(", ");
  const material = `${concept.material.name} with a ${concept.material.finish} finish`;
  return [
    `${concept.title.en}`,
    `${concept.industry} ${concept.form.category}, ${concept.form.variant}`,
    `material ${material}`,
    `motif ${concept.preview.motif_style}, texture ${concept.preview.texture}`,
    palette ? `palette ${palette}` : "",
    "studio product photography, neutral background, soft directional light, high detail",
  ].filter(Boolean).join("; ");
}

async function renderConceptImage(conceptId) {
  const concept = (state.lastConcepts || []).find((row) => row.concept_id === conceptId);
  const target = document.getElementById(`ai-${conceptId}`);
  if (!concept || !target) return;
  target.innerHTML = `<p class="muted">${esc(t("ws.render_pending"))}</p>`;
  try {
    const response = await fetch(`${SIDECAR_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: conceptPrompt(concept), size: "1024x1024", watermark: false }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error((payload.error && payload.error.message) || `HTTP ${response.status}`);
    const record = payload.record;
    target.innerHTML = `<figure class="ai-figure">
      <img src="${SIDECAR_URL}${payload.image_url}" alt="${esc(concept.title.en)}" loading="lazy">
      <figcaption><span class="badge warn">${esc(t("ws.ai_label"))}</span>
        ${esc(record.model)} · ${esc(record.mode)} · sha256 ${esc(record.image_sha256.slice(0, 12))}...</figcaption>
    </figure>`;
  } catch (error) {
    target.innerHTML = `<p class="muted">${esc(t("ws.render_failed"))}: ${esc(error.message)}. ${esc(t("ws.render_hint"))}</p>`;
  }
}

async function renderConceptCopy(conceptId) {
  const concept = (state.lastConcepts || []).find((row) => row.concept_id === conceptId);
  const target = document.getElementById(`copy-${conceptId}`);
  if (!concept || !target) return;
  target.innerHTML = `<p class="muted">${esc(t("ws.copy_pending"))}</p>`;
  const palette = (concept.palette || []).slice(0, 4).map((entry) => entry.hex).join(", ");
  const prompt = [
    "Write a bilingual product description for this craft concept.",
    `Title: ${concept.title.en}`,
    `Industry: ${concept.industry}; form: ${concept.form.category} / ${concept.form.variant}`,
    `Material: ${concept.material.name}, finish ${concept.material.finish}`,
    `Motif: ${concept.preview.motif_style}; palette: ${palette}`,
    'Return exactly two lines: "EN: ..." then "ZH: ...". No extra commentary.',
  ].join("\n");
  try {
    const response = await fetch(`${SIDECAR_URL}/generate_text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, max_tokens: 400 }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error((payload.error && payload.error.message) || `HTTP ${response.status}`);
    const record = payload.record;
    target.innerHTML = `<div class="ai-copy-box">
      <span class="badge warn">${esc(t("ws.ai_label"))}</span>
      <pre>${esc(payload.text)}</pre>
      <p class="muted">${esc(record.model)} · ${esc(record.mode)} · sha256 ${esc(record.text_sha256.slice(0, 12))}...</p>
    </div>`;
  } catch (error) {
    target.innerHTML = `<p class="muted">${esc(t("ws.copy_failed"))}: ${esc(error.message)}. ${esc(t("ws.render_hint"))}</p>`;
  }
}

async function refreshModelStatus() {
  const target = $("#model-status");
  if (!target) return;
  try {
    const response = await fetch(`${SIDECAR_URL}/health`);
    const health = await response.json();
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const label = t("model.status_label");
    const badge = health.mode === "live" ? "ok" : "warn";
    const detail = health.mode === "live" ? `${health.model} / ${health.text_model}` : t("model.status_" + health.mode);
    target.innerHTML = `<span class="badge ${badge}">${esc(label)}: ${esc(health.mode)}</span>
      <span class="muted">${esc(detail)}</span>`;
    if (health.mode !== "live") target.title = health.hint || "";
  } catch (error) {
    target.innerHTML = `<span class="badge bad">${esc(t("model.status_label"))}: ${esc(t("model.status_offline"))}</span>
      <span class="muted">${esc(t("ws.render_hint"))}</span>`;
  }
}

/* -- tabs and chrome ---------------------------------------------------- */
function bindTabs() {
  $$("#tabs .tab").forEach((button) => {
    button.addEventListener("click", () => {
      $$("#tabs .tab").forEach((item) => item.classList.toggle("is-active", item === button));
      $$(".panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === `panel-${button.dataset.tab}`));
      if (button.dataset.tab === "dispatch") {
        refreshDispatch();
        refreshCapacity();
        refreshQuality();
      }
      if (button.dataset.tab === "contracts") refreshReviewQueue();
      if (button.dataset.tab === "enterprise") {
        refreshEnterprise();
        refreshSite();
        refreshCrm();
      }
      if (button.dataset.tab === "ipstudio") refreshIp();
      if (button.dataset.tab === "presale") {
        refreshOrders();
        refreshEditions();
      }
      if (button.dataset.tab === "library" && !$("#lib-results").dataset.loaded) runLibrarySearch();
    });
  });
}

function renderChrome() {
  const spec = state.spec;
  $("#chip-asof").textContent = `${t("app.asof")} ${spec.as_of}`;
  $("#chip-offline").textContent = t("app.offline");
  $("#chip-version").textContent = `${t("app.version")} ${spec.version}`;
  $("#footer-text").textContent = `${spec.counts.concepts} concepts · ${spec.counts.library_assets} assets · ${spec.industries.length} industries · ${spec.contracts.length} contracts · loopback only`;
  document.title = t("app.title");
}

function applyI18n() {
  $$("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  const labels = {
    workstation: t("nav.workstation"),
    library: t("nav.library"),
    presale: t("nav.presale"),
    dispatch: t("nav.dispatch"),
    contracts: t("nav.contracts"),
    enterprise: t("nav.enterprise"),
    ipstudio: t("nav.ipstudio"),
  };
  $$("#tabs .tab").forEach((button) => {
    button.textContent = labels[button.dataset.tab] || button.textContent;
  });
  $("#ws-text").placeholder = t("workstation.brief_placeholder");
  $("#ws-generate").textContent = t("common.generate");
  $("#lib-search").textContent = t("library.search");
  $("#lib-ingest").textContent = t("library.ingest_submit");
  $("#lib-load-sample").textContent = t("library.load_sample");
  $("#order-create").textContent = t("presale.create");
  $("#contracts-commands").textContent = t("contracts.commands_text");
}

/* -- workstation -------------------------------------------------------- */
function fillSelects() {
  const industrySelect = $("#ws-industry");
  industrySelect.innerHTML = state.industries
    .map((row) => `<option value="${esc(row.industry)}">${esc(row.title[state.lang] || row.title.en)}</option>`)
    .join("");
  if (state.industries.some((row) => row.industry === "jewelry")) {
    industrySelect.value = "jewelry";
  }
  $("#ws-style").innerHTML = state.styles
    .map((style) => `<option value="${esc(style.style_id)}">${esc(style.title[state.lang] || style.title.en)}</option>`)
    .join("");
}

function renderReference() {
  const node = $("#ws-reference");
  if (!state.referencePalette.length) {
    node.innerHTML = "";
    return;
  }
  node.innerHTML = `<span class="muted">${esc(t("workstation.extracted"))}</span>${swatches(state.referencePalette)}`;
}

async function generateConcepts() {
  const button = $("#ws-generate");
  button.disabled = true;
  button.textContent = t("common.generating");
  try {
    const body = {
      text: $("#ws-text").value.trim(),
      industry: $("#ws-industry").value,
      style_id: $("#ws-style").value,
      count: Number($("#ws-count").value),
    };
    if (state.referencePalette.length) body.reference_palette = state.referencePalette;
    const data = await api("/api/workstation/generate", { method: "POST", body: JSON.stringify(body) });
    state.lastConcepts = data.concepts;
    $("#ws-concepts").innerHTML = data.concepts.map(conceptCard).join("");
    $("#ws-series").innerHTML = "";
    state.concepts = (await api("/api/concepts")).concepts;
    fillConceptSelect();
    toast(`${data.count} concepts generated`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = t("common.generate");
  }
}

function assessmentHtml(assessment) {
  const failed = (assessment.rule_evaluations || []).filter((row) => row.status === "fail");
  const verdict = assessment.final_verdict;
  const blockers = assessment.blockers || [];
  const fixes = assessment.fixes || [];
  const badge = VERDICT_CLASS[verdict] || "info";
  const review = assessment.artisan || {};
  const rows = failed
    .map(
      (row) => `<div class="rule-row">
        <div class="head"><strong>${esc(row.rule_id)}</strong><span class="badge ${row.severity === "blocker" ? "bad" : "warn"}">${esc(row.severity)}</span></div>
        <p>${esc(row.reason[state.lang] || row.reason.en)}</p>
      </div>`
    )
    .join("");
  const fixList = fixes
    .map((fix) => `<div class="rule-row"><div class="head"><strong>${esc(fix.rule_id)}</strong></div><p class="fix">${esc(fix.text[state.lang] || fix.text.en)}</p></div>`)
    .join("");
  const reviewBlock = review.required
    ? `<div class="rule-row">
        <div class="head"><strong>${esc(t("review.queue"))}</strong><span class="badge ${review.status === "pending" ? "warn" : "ok"}">${esc(review.status)}</span></div>
        <p class="muted">${esc(review.queue_id || "-")} · ${esc(review.reviewer || "-")}${review.notes ? ` · ${esc(review.notes)}` : ""}</p>
        ${
          review.status === "pending"
            ? `<div class="row">
                 <label class="field"><span>Verdict</span>
                   <select id="review-verdict">
                     <option value="manufacturable">manufacturable</option>
                     <option value="conditionally_manufacturable">conditionally_manufacturable</option>
                     <option value="not_manufacturable">not_manufacturable</option>
                   </select>
                 </label>
                 <label class="field grow"><span>${esc(t("review.reason"))}</span><input type="text" id="review-reason"></label>
                 <button data-action="review-decide" data-queue="${esc(review.queue_id)}">${esc(t("review.decide"))}</button>
               </div>`
            : ""
        }
      </div>`
    : "";
  return `<div class="verdict">
      <span class="big">${esc(t(`status.${verdict}`) === `status.${verdict}` ? verdict : t(`status.${verdict}`))}</span>
      <span class="badge ${badge}">${esc(verdict)}</span>
      <span class="muted">${esc(assessment.workshop_id)} · ${esc(assessment.concept_id)} · ${esc(assessment.assessment_id)}</span>
    </div>
    <div class="muted">${esc(t("workstation.facts"))}: ${Object.keys(assessment.facts).length} · ${esc(assessment.reproducibility.rules_version)} · ${esc(assessment.reproducibility.facts_hash.slice(0, 12))}</div>
    ${blockers.length ? `<div><strong>${esc(t("workstation.blockers"))}:</strong> ${esc(blockers.join(", "))}</div>` : `<div class="muted">${esc(t("workstation.no_issues"))}</div>`}
    <div class="rules-hit">${rows}</div>
    ${fixes.length ? `<h3>${esc(t("workstation.fixes"))}</h3><div class="rules-hit">${fixList}</div>` : ""}
    ${reviewBlock}`;
}

async function assessConcept(conceptId) {
  const target = $("#ws-assessment");
  target.innerHTML = `<p class="muted">${esc(t("common.loading"))}...</p>`;
  try {
    const data = await api("/api/assess", {
      method: "POST",
      body: JSON.stringify({ concept_id: conceptId }),
    });
    target.innerHTML = assessmentHtml(data.assessment);
    await refreshReviewQueue();
  } catch (error) {
    target.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function expandSeries(conceptId) {
  try {
    const data = await api("/api/workstation/series", {
      method: "POST",
      body: JSON.stringify({ concept_id: conceptId }),
    });
    $("#ws-series").innerHTML = data.series.map(conceptCard).join("");
    state.concepts = (await api("/api/concepts")).concepts;
    fillConceptSelect();
    toast(`${data.count} SKUs expanded`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- library ------------------------------------------------------------ */
function licenseBadge(license) {
  const ok = license.ok;
  return `<span class="badge ${ok ? "ok" : "bad"}">${esc(ok ? t("library.valid") : t("library.expired"))}</span>`;
}

function assetCard(hit) {
  const asset = hit.asset;
  const license = hit.license;
  const scope = (license.usage_scope || []).join(", ");
  return `<article class="asset">
    <header><h4>${esc(asset.title[state.lang] || asset.title.en)}</h4><span class="id">${esc(asset.asset_id)}</span></header>
    ${swatches(asset.palette || [])}
    <div class="muted">${esc(asset.industries.join(", "))} · ${esc(asset.medium)} · ${esc(asset.tags.join(", "))}</div>
    <div>${licenseBadge(license)} <span class="badge info">${esc(license.source_type)}</span></div>
    <div class="muted">${esc(t("library.scope"))}: ${esc(scope)}</div>
    <div class="muted">${esc(t("library.window"))}: ${esc(license.window.from)} → ${esc(license.window.to)}</div>
    <div class="muted">score ${esc(hit.score)}${hit.matched && hit.matched.length ? ` · ${esc(hit.matched.join(", "))}` : ""}</div>
  </article>`;
}

async function runLibrarySearch() {
  const params = new URLSearchParams();
  if ($("#lib-q").value.trim()) params.set("q", $("#lib-q").value.trim());
  if ($("#lib-tags").value.trim()) params.set("tags", $("#lib-tags").value.trim());
  if ($("#lib-palette").value.trim()) params.set("palette", $("#lib-palette").value.trim());
  if ($("#lib-family").value) params.set("family", $("#lib-family").value);
  if ($("#lib-symmetry").value) params.set("symmetry", $("#lib-symmetry").value);
  if ($("#lib-weight").value) params.set("weight", $("#lib-weight").value);
  const industry = $("#ws-industry").value;
  if (industry) params.set("industry", industry);
  try {
    const data = await api(`/api/library/search?${params.toString()}`);
    $("#lib-results").innerHTML = data.results.length
      ? data.results.map(assetCard).join("")
      : `<p class="muted">${esc(t("common.empty"))}</p>`;
    $("#lib-results").dataset.loaded = "1";
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

const REJECTION_SAMPLES = [
  {
    label: "missing licensing source",
    payload: {
      asset_id: "PA-JW-0911",
      title: { zh: "缺来源样本", en: "Missing source sample" },
      industries: ["jewelry"],
      medium: "pattern",
      tags: ["demo"],
      palette: ["#C9A227"],
      preview: { motif_style: "fret", texture: "polished", gradient_angle_deg: 45 },
      license: { usage_scope: ["commercial_product"] },
      traditional_prototype: false,
      religious_site_names: [],
      review: { status: "auto_checked" },
      created_at: "2026-10-22T00:00:00Z",
    },
  },
  {
    label: "empty usage scope",
    payload: {
      asset_id: "PA-JW-0912",
      title: { zh: "空范围样本", en: "Empty scope sample" },
      industries: ["jewelry"],
      medium: "pattern",
      tags: ["demo"],
      license: { source_type: "self_produced", usage_scope: [] },
      traditional_prototype: false,
      religious_site_names: [],
      review: { status: "auto_checked" },
      created_at: "2026-10-22T00:00:00Z",
    },
  },
  {
    label: "exclusive claim on heritage",
    payload: {
      asset_id: "PA-JW-0913",
      title: { zh: "独占传统样本", en: "Exclusive heritage sample" },
      industries: ["heritage"],
      medium: "pattern",
      tags: ["demo"],
      license: {
        source_type: "traditional_heritage",
        licensor: "Heritage registry (synthetic)",
        license_id: "LIC-SYN-DEMO",
        usage_scope: ["commercial_product"],
        valid_from: "2026-01-01T00:00:00Z",
        valid_to: "2030-01-01T00:00:00Z",
        exclusive: true,
      },
      traditional_prototype: true,
      religious_site_names: [],
      review: { status: "content_reviewed" },
      created_at: "2026-10-22T00:00:00Z",
    },
  },
];

function loadRejectionSample() {
  const index = (loadRejectionSample.index = ((loadRejectionSample.index || 0) + 1) % REJECTION_SAMPLES.length);
  $("#lib-json").value = JSON.stringify(REJECTION_SAMPLES[index].payload, null, 1);
  toast(`sample loaded: ${REJECTION_SAMPLES[index].label}`, "ok");
}

async function ingestAsset() {
  const target = $("#lib-ingest-result");
  let payload;
  try {
    payload = JSON.parse($("#lib-json").value);
  } catch (error) {
    toast(`invalid JSON: ${error.message}`);
    return;
  }
  try {
    const data = await api("/api/library/ingest", { method: "POST", body: JSON.stringify(payload) });
    target.innerHTML = `<div class="rule-row">
      <div class="head"><strong>${esc(t("library.accepted"))}</strong><span class="badge ok">${esc(data.asset.asset_id)}</span></div>
      <p>${esc(data.license.source_type)} · ${esc((data.license.usage_scope || []).join(", "))}</p>
    </div>`;
    await runLibrarySearch();
  } catch (error) {
    target.innerHTML = `<div class="rule-row">
      <div class="head"><strong>${esc(t("library.rejected"))}</strong><span class="badge bad">validation</span></div>
      <p>${esc(error.message)}</p>
    </div>`;
    toast(`${t("library.rejected")}: ${error.message}`);
  }
}

/* -- customisation and editions ---------------------------------------- */
function conceptsFor(industry) {
  return state.concepts.filter((row) => !industry || row.industry === industry);
}

function fillCustomization() {
  const industrySelect = $("#custom-industry");
  industrySelect.innerHTML = state.industries
    .map((row) => `<option value="${esc(row.industry)}">${esc(row.title[state.lang] || row.title.en)}</option>`)
    .join("");
  if (state.industries.some((row) => row.industry === "jewelry")) industrySelect.value = "jewelry";
  industrySelect.onchange = () => {
    fillCustomConcepts();
    renderOptionGroups();
  };
  fillCustomConcepts();
  renderOptionGroups();
}

function fillCustomConcepts() {
  const industry = $("#custom-industry").value;
  const rows = conceptsFor(industry);
  const options = rows
    .map(
      (row) =>
        `<option value="${esc(row.concept_id)}">${esc(row.concept_id)} · ${esc(row.title[state.lang] || row.title.en)}</option>`
    )
    .join("");
  $("#custom-concept").innerHTML = options;
  $("#edition-concept").innerHTML = options;
}

async function renderOptionGroups() {
  const industry = $("#custom-industry").value;
  const container = $("#custom-options");
  try {
    const catalog = await api(`/api/customization/catalog?industry=${encodeURIComponent(industry)}`);
    state.catalog[industry] = catalog;
    container.innerHTML = catalog.groups
      .map(
        (group) => `<div class="option-group">
          <h4>${esc(group.label[state.lang] || group.label.en)}</h4>
          ${group.options
            .map(
              (option, index) => `<label>
                <input type="radio" name="opt-${esc(group.group_id)}" value="${esc(option.option_id)}" ${index === 0 ? "checked" : ""}>
                <span>${esc(option.label[state.lang] || option.label.en)}</span>
                <span class="delta">${option.price_delta_bp > 0 ? "+" : ""}${(option.price_delta_bp / 100).toFixed(1)}%</span>
              </label>`
            )
            .join("")}
        </div>`
      )
      .join("");
  } catch (error) {
    container.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
  }
}

function selectedOptions() {
  return $$("#custom-options .option-group input[type=radio]:checked").map((input) => ({
    group_id: input.name.replace(/^opt-/, ""),
    option_id: input.value,
  }));
}

async function previewCustomization() {
  const conceptId = $("#custom-concept").value;
  const selections = selectedOptions();
  const target = $("#custom-result");
  if (!conceptId || !selections.length) {
    toast("pick a concept and at least one option");
    return;
  }
  target.innerHTML = `<p class="muted">${esc(t("common.loading"))}...</p>`;
  try {
    const data = await api("/api/customization/preview", {
      method: "POST",
      body: JSON.stringify({ concept_id: conceptId, selections }),
    });
    const choice = data.choice;
    const ok = choice.feasibility.ok;
    const quote = data.quote;
    target.innerHTML = `<div class="rule-row">
      <div class="head"><strong>${esc(t("custom.delta"))}</strong><span class="badge ${ok ? "ok" : "bad"}">${esc(ok ? "feasible" : "infeasible")}</span></div>
      <p>${esc(t("custom.unit"))}: ${esc(choice.amounts.base_unit_price_cents)} → ${esc(choice.amounts.unit_price_cents)} cents (${choice.amounts.delta_cents >= 0 ? "+" : ""}${esc(choice.amounts.delta_cents)})</p>
      <p>${esc(t("custom.verdict"))}: ${esc(quote ? quote.verdict : "not_manufacturable")} · ${esc(quote ? quote.workshop_id : "-")} · ${esc(quote ? quote.promised_delivery_at : "-")}</p>
      ${ok ? "" : `<p class="badge bad">${esc(t("custom.infeasible"))}</p><p class="muted">${esc((choice.feasibility.blockers || []).join(", "))}</p>`}
    </div>`;
  } catch (error) {
    target.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function createCustomOrder() {
  const conceptId = $("#custom-concept").value;
  const selections = selectedOptions();
  if (!conceptId || !selections.length) {
    toast("pick a concept and at least one option");
    return;
  }
  try {
    const data = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({ concept_id: conceptId, selections, model: "participatory_customization" }),
    });
    state.selectedOrder = data.order.order_id;
    await refreshOrders();
    await showOrder(data.order.order_id);
    toast(`${t("custom.applied")} ${data.order.order_id}`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function refreshEditions() {
  try {
    const data = await api("/api/editions");
    renderEditions(data.editions);
    renderArchive(data.records);
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

function renderEditions(rows) {
  const target = $("#edition-list");
  if (!rows.length) {
    target.innerHTML = `<p class="muted">${esc(t("edition.none"))}</p>`;
    return;
  }
  target.innerHTML = rows
    .map((edition) => {
      const issued = edition.numbering.issued.map((row) => row.number).join(", ") || "-";
      return `<div class="rule-row">
        <div class="head"><strong>${esc(edition.edition_id)}</strong><span class="badge info">${esc(edition.status)}</span></div>
        <p>${esc(edition.title[state.lang] || edition.title.en)} · ${esc(edition.artist.name)} · ${esc(t("edition.size"))} ${esc(edition.size)}</p>
        <p class="muted">${esc(t("edition.issued"))}: ${esc(issued)} / ${esc(edition.size)}</p>
        <div class="row">
          <label class="field"><span>${esc(t("edition.owner_id"))}</span><input type="text" id="owner-id-${esc(edition.edition_id)}" value="OWNER-C1"></label>
          <label class="field grow"><span>${esc(t("edition.owner_name"))}</span><input type="text" id="owner-name-${esc(edition.edition_id)}" value="Collector One"></label>
          <button data-action="edition-issue" data-edition="${esc(edition.edition_id)}">${esc(t("edition.issue"))}</button>
        </div>
      </div>`;
    })
    .join("");
}

function renderArchive(rows) {
  const target = $("#collector-archive");
  if (!rows.length) {
    target.innerHTML = `<p class="muted">${esc(t("common.empty"))}</p>`;
    return;
  }
  target.innerHTML = rows
    .map(
      (record) => `<div class="rule-row">
        <div class="head"><strong>${esc(record.certificate_id)}</strong><span class="badge info">#${esc(record.edition_number)}</span></div>
        <p class="muted">${esc(record.edition_id)} · ${esc(t("edition.owner"))} ${esc(record.owner.display_name)} · ${esc(record.provenance_count)} hops</p>
        <p class="mono" style="font-size:11px">${esc(record.certificate_hash.slice(0, 32))}...</p>
        <div class="row">
          <label class="field"><span>${esc(t("edition.owner_id"))}</span><input type="text" id="transfer-id-${esc(record.record_id)}" value="OWNER-G2"></label>
          <label class="field grow"><span>${esc(t("edition.owner_name"))}</span><input type="text" id="transfer-name-${esc(record.record_id)}" value="Collector G"></label>
          <button data-action="collector-transfer" data-record="${esc(record.record_id)}">${esc(t("edition.transfer"))}</button>
        </div>
      </div>`
    )
    .join("");
}

async function createEdition() {
  const conceptId = $("#edition-concept").value;
  const size = Number($("#edition-size").value || 5);
  try {
    const data = await api("/api/editions", {
      method: "POST",
      body: JSON.stringify({
        concept_id: conceptId,
        size,
        artist: { artist_id: "ARTIST-01", name: "Studio Lin (synthetic)", royalty_rate_bp: 800 },
      }),
    });
    await refreshEditions();
    toast(`${data.edition.edition_id} opened with ${data.edition.size} numbers`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function issueEdition(editionId) {
  const ownerId = $(`#owner-id-${editionId}`) ? $(`#owner-id-${editionId}`).value : "OWNER-C1";
  const ownerName = $(`#owner-name-${editionId}`) ? $(`#owner-name-${editionId}`).value : "Collector One";
  const orderId = state.orders.length ? state.orders[state.orders.length - 1].order_id : "";
  if (!orderId) {
    toast("create an order first so the certificate can reference it");
    return;
  }
  try {
    await api(`/api/editions/${editionId}/issue`, {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, owner: { owner_id: ownerId, display_name: ownerName } }),
    });
    await refreshEditions();
    toast(`certificate issued for ${editionId}`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function transferCollector(recordId) {
  const ownerId = $(`#transfer-id-${recordId}`) ? $(`#transfer-id-${recordId}`).value : "";
  const ownerName = $(`#transfer-name-${recordId}`) ? $(`#transfer-name-${recordId}`).value : "";
  try {
    await api(`/api/collectors/${recordId}/transfer`, {
      method: "POST",
      body: JSON.stringify({ owner_id: ownerId, display_name: ownerName, note: "transfer recorded in the prototype" }),
    });
    await refreshEditions();
    toast(`${recordId} transferred to ${ownerName}`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function refreshCapacity() {
  try {
    const data = await api("/api/capacity/board");
    const rows = data.schedules
      .map((schedule) => {
        const peak = schedule.utilization.reduce(
          (best, row) => Math.max(best, row.capacity_minutes ? Math.round((row.booked_minutes * 100) / row.capacity_minutes) : 0),
          0
        );
        const booked = schedule.slots.reduce((sum, slot) => sum + slot.minutes, 0);
        return `<tr>
          <td>${esc(schedule.workshop_id)}</td>
          <td class="num">${esc(schedule.capacity_per_day_minutes)}</td>
          <td class="num">${esc(schedule.slots.length)}</td>
          <td class="num">${esc(booked)}</td>
          <td class="num">${peak}%</td>
        </tr>`;
      })
      .join("");
    $("#capacity-board").innerHTML = `<table>
      <thead><tr><th>${esc(t("capacity.workshop"))}</th><th class="num">capacity</th><th class="num">${esc(t("capacity.slots"))}</th><th class="num">${esc(t("capacity.booked"))}</th><th class="num">${esc(t("capacity.peak"))}</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function refreshQuality() {
  try {
    const data = await api("/api/quality/records");
    const target = $("#quality-records");
    if (!data.records.length) {
      target.innerHTML = `<p class="muted">${esc(t("quality.none"))}</p>`;
      return;
    }
    target.innerHTML = `<table>
      <thead><tr><th>${esc(t("quality.record"))}</th><th>checkpoint</th><th>${esc(t("quality.verdict"))}</th><th>${esc(t("quality.defects"))}</th></tr></thead>
      <tbody>${data.records
        .map(
          (record) => `<tr>
            <td>${esc(record.qc_id)}<div class="muted">${esc(record.work_order_id)}</div></td>
            <td>${esc(record.checkpoint_id)}</td>
            <td><span class="badge ${record.verdict === "pass" ? "ok" : "bad"}">${esc(record.verdict)}</span></td>
            <td>${esc(record.defects.map((defect) => `${defect.code} x${defect.count}`).join(", ") || "-")}</td>
          </tr>`
        )
        .join("")}</tbody></table>`;
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- orders ------------------------------------------------------------- */
function fillConceptSelect() {
  const select = $("#order-concept");
  if (!select) return;
  select.innerHTML = state.concepts
    .map(
      (row) =>
        `<option value="${esc(row.concept_id)}">${esc(row.concept_id)} · ${esc(row.title[state.lang] || row.title.en)}</option>`
    )
    .join("");
}

async function refreshOrders() {
  try {
    const data = await api("/api/orders");
    state.orders = data.orders;
    renderOrderList();
    if (state.selectedOrder) await showOrder(state.selectedOrder);
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

function renderOrderList() {
  const target = $("#order-list");
  if (!state.orders.length) {
    target.innerHTML = `<p class="muted">${esc(t("presale.none"))}</p>`;
    return;
  }
  target.innerHTML = state.orders
    .map((order) => {
      const amounts = order.amounts;
      const statusClass = order.status === "settled" ? "ok" : order.status === "refunded" ? "bad" : "info";
      return `<div class="order">
        <header><h4>${esc(order.order_id)}</h4><span class="badge ${statusClass}">${esc(order.status)}</span></header>
        <div class="muted">${esc(order.items[0].title[state.lang] || order.items[0].title.en)}</div>
        <div class="muted">${esc(t("presale.total"))} ${esc((amounts.total_cents / 100).toFixed(2))} USD · ${esc(t("presale.deposit"))} ${esc((amounts.deposit_cents / 100).toFixed(2))}</div>
        <div class="actions"><button data-action="order-select" data-order="${esc(order.order_id)}">${esc(t("common.show"))}</button></div>
      </div>`;
    })
    .join("");
}

function splitBar(amounts) {
  const total = amounts.total_cents || 1;
  const rows = [
    ["designer", amounts.designer_share_cents, "#c9a227"],
    ["factory", amounts.factory_share_cents, "#2e6f7e"],
    ["ip", amounts.ip_share_cents, "#8c5a1e"],
    ["platform", amounts.platform_fee_cents, "#5e6a72"],
  ];
  return `<div class="split-bar">${rows
    .map(([, cents, color]) => `<span style="width:${((cents / total) * 100).toFixed(2)}%;background:${color}"></span>`)
    .join("")}</div>
    <div class="legend">${rows
      .map(([name, cents, color]) => `<span><i style="background:${color}"></i>${name} ${(cents / 100).toFixed(2)}</span>`)
      .join("")}</div>`;
}

function timeline(events) {
  if (!events.length) return `<p class="muted">${esc(t("common.empty"))}</p>`;
  return `<div class="timeline">${events
    .map(
      (event) => `<div class="event">
        <span class="at">${esc(event.at.slice(11, 16))}</span>
        <span><strong>${esc(event.type)}</strong> <span class="muted">${esc(event.from_status)} → ${esc(event.to_status)}</span> <span class="muted">${esc(event.actor.id)}</span></span>
        <span class="hash">${esc(event.hash.slice(0, 10))}</span>
      </div>`
    )
    .join("")}</div>`;
}

function settlementBlock(settlement) {
  if (!settlement) return "";
  return `<h3>${esc(t("presale.settlement"))}</h3>
    <table>
      <thead><tr><th>party</th><th class="num">rate</th><th class="num">cents</th></tr></thead>
      <tbody>${settlement.payout_lines
        .map(
          (line) =>
            `<tr><td>${esc(line.party)}</td><td class="num">${(line.rate_bp / 100).toFixed(2)}%</td><td class="num">${esc(line.amount_cents)}</td></tr>`
        )
        .join("")}</tbody>
    </table>
    <p class="muted">total ${esc(settlement.total_cents)} · remainder ${esc(settlement.remainder_cents)} · reconciliation delta ${esc(settlement.reconciliation.delta_cents)}</p>`;
}

async function showOrder(orderId) {
  state.selectedOrder = orderId;
  const target = $("#order-detail");
  try {
    const data = await api(`/api/orders/${orderId}`);
    const order = data.order;
    const actions = (data.available_events || [])
      .map(
        (row) =>
          `<button data-action="order-advance" data-order="${esc(orderId)}" data-event="${esc(row.event)}" data-actor="${esc(row.actors[0])}">${esc(row.event)} → ${esc(row.to)}</button>`
      )
      .join("");
    const refund = order.refund;
    const dispute = order.dispute;
    target.innerHTML = `<div class="verdict"><span class="big">${esc(order.order_id)}</span><span class="badge info">${esc(order.status)}</span>
        <span class="muted">${esc(order.model)} · ${esc(order.buyer.id)}</span></div>
      <h3>${esc(t("presale.amounts"))}</h3>
      <table>
        <tbody>
          <tr><td>subtotal</td><td class="num">${esc(order.amounts.subtotal_cents)}</td></tr>
          <tr><td>customisation fee</td><td class="num">${esc(order.amounts.customization_fee_cents)}</td></tr>
          <tr><td>total</td><td class="num"><strong>${esc(order.amounts.total_cents)}</strong></td></tr>
          <tr><td>deposit</td><td class="num">${esc(order.amounts.deposit_cents)}</td></tr>
        </tbody>
      </table>
      <h3>${esc(t("presale.split"))}</h3>
      ${splitBar(order.amounts)}
      <div class="actions">${actions || `<span class="muted">no transition available</span>`}</div>
      <h3>${esc(t("presale.refund"))}</h3>
      <div class="muted">status: ${esc(refund.status)} · amount ${esc(refund.amount_cents)}${refund.reason ? ` · ${esc(refund.reason)}` : ""}</div>
      <div class="row">
        <label class="field grow"><span>${esc(t("presale.reason"))}</span><input type="text" id="refund-reason"></label>
        <button data-action="refund-request" data-order="${esc(orderId)}">${esc(t("presale.refund_request"))}</button>
        <button data-action="refund-approve" data-order="${esc(orderId)}">${esc(t("presale.refund_approve"))}</button>
        <button data-action="refund-execute" data-order="${esc(orderId)}">${esc(t("presale.refund_execute"))}</button>
      </div>
      <h3>${esc(t("presale.dispute"))}</h3>
      <div class="muted">status: ${esc(dispute.status)}${dispute.reason ? ` · ${esc(dispute.reason)}` : ""}${
        (dispute.qc_record_ids || []).length
          ? ` · ${esc(t("presale.dispute_evidence"))}: ${esc(dispute.qc_record_ids.join(", "))}`
          : ""
      }</div>
      <div id="dispute-evidence" class="stack"></div>
      <div class="row">
        <label class="field grow"><span>${esc(t("presale.reason"))}</span><input type="text" id="dispute-reason"></label>
        <button data-action="dispute-open" data-order="${esc(orderId)}">${esc(t("presale.dispute_open"))}</button>
      </div>
      <div class="row">
        <label class="field"><span>${esc(t("presale.resolution"))}</span>
          <select id="dispute-resolution">
            <option value="rework">rework</option>
            <option value="split">split settlement</option>
            <option value="refund">full refund</option>
          </select>
        </label>
        <label class="field grow"><span>${esc(t("presale.note"))}</span><input type="text" id="dispute-note"></label>
        <button data-action="dispute-resolve" data-order="${esc(orderId)}">${esc(t("presale.dispute_resolve"))}</button>
      </div>
      ${settlementBlock(data.settlement)}
      <h3>${esc(t("presale.timeline"))}</h3>
      ${timeline(data.events)}`;
    renderDisputeEvidence(order);
  } catch (error) {
    target.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function renderDisputeEvidence(order) {
  const container = $("#dispute-evidence");
  if (!container) return;
  const workOrderId = order.items && order.items[0] ? order.items[0].work_order_id : null;
  if (!workOrderId) {
    container.innerHTML = "";
    return;
  }
  try {
    const data = await api(`/api/quality/records?work_order_id=${encodeURIComponent(workOrderId)}`);
    if (!data.records.length) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = `<div class="muted">${esc(t("presale.dispute_evidence_hint"))}</div>` +
      data.records
        .map(
          (record) => `<label class="check"><input type="checkbox" name="dispute-qc" value="${esc(record.qc_id)}">
            <span>${esc(record.qc_id)} · ${esc(record.checkpoint_id)} · <span class="badge ${record.verdict === "pass" ? "ok" : "bad"}">${esc(record.verdict)}</span></span></label>`
        )
        .join("");
  } catch (error) {
    container.innerHTML = "";
  }
}

async function advanceOrder(orderId, event, actor) {
  try {
    const data = await api(`/api/orders/${orderId}/advance`, {
      method: "POST",
      body: JSON.stringify({ event, actor_kind: actor || "system", actor_id: actor || "system" }),
    });
    toast(`${event} → ${data.order.status}`, "ok");
    await refreshOrders();
    await showOrder(orderId);
    await refreshDispatch();
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function refundAction(orderId, action) {
  const reason = $("#refund-reason") ? $("#refund-reason").value.trim() : "";
  try {
    await api(`/api/orders/${orderId}/refund`, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    });
    toast(`refund ${action}`, "ok");
    await refreshOrders();
    await showOrder(orderId);
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function disputeAction(orderId, action) {
  try {
    const body = { action };
    if (action === "open") {
      body.reason = $("#dispute-reason") ? $("#dispute-reason").value.trim() : "";
      body.qc_record_ids = $$('input[name="dispute-qc"]:checked').map((input) => input.value);
    } else {
      body.resolution = $("#dispute-resolution") ? $("#dispute-resolution").value : "split";
      body.note = $("#dispute-note") ? $("#dispute-note").value.trim() : "";
    }
    await api(`/api/orders/${orderId}/dispute`, { method: "POST", body: JSON.stringify(body) });
    toast(`dispute ${action}`, "ok");
    await refreshOrders();
    await showOrder(orderId);
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- dispatch ----------------------------------------------------------- */
async function refreshDispatch() {
  const board = $("#dispatch-board");
  const detail = $("#dispatch-detail");
  try {
    const data = await api("/api/dispatch/board");
    if (!data.board.length) {
      board.innerHTML = `<p class="muted">${esc(t("common.empty"))}</p>`;
      return;
    }
    board.innerHTML = `<table>
      <thead><tr><th>order</th><th>status</th><th>workshop</th><th>promised</th><th class="num">total</th><th></th></tr></thead>
      <tbody>${data.board
        .map(
          (row) => `<tr>
            <td>${esc(row.order_id)}<div class="muted">${esc(row.concept_id)}</div></td>
            <td><span class="badge info">${esc(row.status)}</span></td>
            <td>${esc(row.workshop_id || "-")}</td>
            <td>${esc(row.promised_delivery_at || "-")}</td>
            <td class="num">${esc(row.total_cents)}</td>
            <td><button data-action="dispatch-select" data-work-order="${esc(row.workshop_id ? row.order_id : "")}">${esc(t("common.show"))}</button></td>
          </tr>`
        )
        .join("")}</tbody></table>`;

    const workOrders = data.work_orders || [];
    detail.innerHTML = workOrders.length
      ? workOrders
          .map((wo) => {
            const bom = wo.bom
              .map(
                (line) =>
                  `<tr><td>${esc(line.line_id)}</td><td>${esc(line.material)}</td><td>${esc(line.spec)}</td><td class="num">${esc(line.quantity)} ${esc(line.unit)}</td><td class="num">${esc(line.unit_cost_cents)}</td></tr>`
              )
              .join("");
            const route = wo.process_steps
              .map(
                (step) =>
                  `<tr><td>${esc(step.step_id)}</td><td>${esc(step.name[state.lang] || step.name.en)}</td><td>${esc(step.process)}</td><td>${esc(step.equipment_id)}</td><td class="num">${esc(step.est_minutes)}</td></tr>`
              )
              .join("");
            const qc = wo.qc_checkpoints
              .map(
                (item) =>
                  `<tr><td>${esc(item.checkpoint_id)}</td><td>${esc(item.name[state.lang] || item.name.en)}</td><td>${esc(item.method)}</td><td>${esc(item.pass_criteria)}</td><td><span class="badge ${item.status === "passed" ? "ok" : item.status === "failed" ? "bad" : ""}">${esc(item.status)}</span></td></tr>`
              )
              .join("");
            return `<div class="wo">
              <div class="verdict"><span class="big">${esc(wo.work_order_id)}</span><span class="badge info">${esc(wo.status)}</span><span class="muted">${esc(wo.order_id)} · ${esc(wo.workshop_id)} · ${esc(t("dispatch.promised"))} ${esc(wo.promised_delivery_at)}</span></div>
              <h3>${esc(t("dispatch.bom"))}</h3>
              <table><thead><tr><th>line</th><th>material</th><th>spec</th><th class="num">qty</th><th class="num">unit cents</th></tr></thead><tbody>${bom}</tbody></table>
              <h3>${esc(t("dispatch.route"))}</h3>
              <table><thead><tr><th>op</th><th>name</th><th>process</th><th>equipment</th><th class="num">minutes</th></tr></thead><tbody>${route}</tbody></table>
              <h3>${esc(t("dispatch.qc"))}</h3>
              <table><thead><tr><th>id</th><th>checkpoint</th><th>method</th><th>pass criteria</th><th>status</th></tr></thead><tbody>${qc}</tbody></table>
              <details><summary>${esc(t("dispatch.constraints"))}</summary><ul>${(wo.process_steps[0].constraints || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></details>
            </div>`;
          })
          .join("")
      : `<p class="muted">${esc(t("dispatch.none"))}</p>`;
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- contracts and rules ------------------------------------------------ */
function renderContracts() {
  const spec = state.spec;
  $("#contracts-list").innerHTML = `<table>
    <thead><tr><th>contract</th><th>version</th><th>${esc(t("contracts.invariants"))}</th><th>${esc(t("contracts.requirements"))}</th></tr></thead>
    <tbody>${spec.contracts
      .map(
        (row) =>
          `<tr><td>${esc(row.id)}<div class="muted mono">${esc(row.file)}</div></td><td>${esc(row.version)}</td><td>${esc((row.invariants || []).join(", ") || "-")}</td><td>${esc((row.requirements || []).join(", "))}</td></tr>`
      )
      .join("")}</tbody></table>
    <p class="muted">${esc(spec.industries.map((row) => `${row.industry}: ${row.rules} rules / ${row.facts} facts / ${row.rule_version}`).join(" · "))}</p>`;

  $("#contracts-artifacts").textContent = [
    "out/contract_report.json",
    "out/rules_report.json",
    "out/workstation_catalog.json",
    "out/library_snapshot.json",
    "out/assessment_results.json",
    "out/assessment_matrix.md",
    "out/order_trace.jsonl",
    "out/settlement_report.md",
    "out/coverage_report.md",
    "out/hash_manifest.json",
  ].join("\n");
}

async function refreshRules() {
  try {
    const data = await api("/api/rules");
    const byIndustry = {};
    data.rules.forEach((rule) => {
      (byIndustry[rule.industry] = byIndustry[rule.industry] || []).push(rule);
    });
    $("#rules-list").innerHTML = Object.keys(byIndustry)
      .sort()
      .map((industry) => {
        const rows = byIndustry[industry]
          .map(
            (rule) => `<details>
              <summary><strong>${esc(rule.rule_id)}</strong> · ${esc(rule.title[state.lang] || rule.title.en)} <span class="badge ${rule.severity === "blocker" ? "bad" : "warn"}">${esc(rule.severity)}</span></summary>
              <pre class="code" id="rule-${esc(rule.rule_id)}">${esc(t("common.loading"))}</pre>
              <button data-action="rule-explain" data-rule="${esc(rule.rule_id)}" data-industry="${esc(industry)}">${esc(t("contracts.explain"))}</button>
            </details>`
          )
          .join("");
        return `<h3>${esc(industry)} (${byIndustry[industry].length})</h3><div class="stack">${rows}</div>`;
      })
      .join("");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function explainRule(ruleId) {
  try {
    const data = await api(`/api/rules/${ruleId}`);
    const target = $(`#rule-${ruleId}`);
    if (target) target.textContent = JSON.stringify(data, null, 1);
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

async function refreshReviewQueue() {
  try {
    const data = await api("/api/reviews/queue");
    const target = $("#review-queue");
    if (!target) return;
    if (!data.items.length) {
      target.innerHTML = `<p class="muted">${esc(t("common.empty"))}</p>`;
      return;
    }
    target.innerHTML = data.items
      .map((item) => {
        const badge = item.status === "pending" ? "warn" : item.status === "overridden" ? "info" : "ok";
        const form =
          item.status === "pending"
            ? `<div class="row">
                 <label class="field"><span>Verdict</span>
                   <select id="review-verdict-${esc(item.queue_id)}">
                     <option value="manufacturable">manufacturable</option>
                     <option value="conditionally_manufacturable">conditionally_manufacturable</option>
                     <option value="not_manufacturable">not_manufacturable</option>
                   </select>
                 </label>
                 <label class="field grow"><span>${esc(t("review.reason"))}</span><input type="text" id="review-reason-${esc(item.queue_id)}"></label>
                 <button data-action="review-decide" data-queue="${esc(item.queue_id)}" data-scope="queue">${esc(t("review.decide"))}</button>
               </div>`
            : "";
        return `<div class="rule-row">
          <div class="head"><strong>${esc(item.queue_id)}</strong><span class="badge ${badge}">${esc(item.status)}</span></div>
          <p class="muted">${esc(item.assessment_id)} · ${esc(item.concept_id)} · ${esc(item.rule_ids.join(", "))} · auto ${esc(item.auto_verdict)}</p>
          ${item.decision ? `<p>${esc(item.decision.verdict)} — ${esc(item.decision.reason)}</p>` : ""}
          ${form}
        </div>`;
      })
      .join("");
  } catch (error) {
    /* the queue is informational; a failure should not break the page */
  }
}

async function decideReview(queueId) {
  const verdictInput = $(`#review-verdict-${queueId}`) || $("#review-verdict");
  const reasonInput = $(`#review-reason-${queueId}`) || $("#review-reason");
  const verdict = verdictInput ? verdictInput.value : "";
  const reason = reasonInput ? reasonInput.value.trim() : "";
  try {
    const data = await api(`/api/reviews/${queueId}/decide`, {
      method: "POST",
      body: JSON.stringify({ verdict, reason }),
    });
    if ($("#ws-assessment") && data.assessment) {
      $("#ws-assessment").innerHTML = assessmentHtml(data.assessment);
    }
    await refreshReviewQueue();
    toast(`review ${queueId}: ${data.review.status}`, "ok");
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- wiring ------------------------------------------------------------- */
/* -- enterprise service layer ------------------------------------------- */
function assetSvg(asset) {
  const width = asset.resolution.width;
  const height = asset.resolution.height;
  const layers = asset.recipe.layers
    .map((layer) => {
      const g = layer.geometry.map((value) => Number(value));
      const common = `fill="${esc(layer.fill)}" stroke="${esc(layer.stroke)}" stroke-width="${Number(layer.stroke_width)}" opacity="${(Number(layer.opacity_bp) / 10000).toFixed(4)}"`;
      const pairs = [];
      for (let index = 0; index < g.length; index += 2) pairs.push(`${g[index]},${g[index + 1]}`);
      if (layer.shape === "rect") return `<rect x="${g[0]}" y="${g[1]}" width="${g[2]}" height="${g[3]}" ${common}/>`;
      if (layer.shape === "circle") return `<circle cx="${g[0]}" cy="${g[1]}" r="${g[2]}" ${common}/>`;
      if (layer.shape === "ellipse") return `<ellipse cx="${g[0]}" cy="${g[1]}" rx="${g[2]}" ry="${g[3]}" ${common}/>`;
      if (layer.shape === "line") return `<line x1="${g[0]}" y1="${g[1]}" x2="${g[2]}" y2="${g[3]}" ${common}/>`;
      if (layer.shape === "polygon") return `<polygon points="${pairs.join(" ")}" ${common}/>`;
      return `<path d="M ${pairs.join(" L ")}${layer.closed ? " Z" : ""}" ${common}/>`;
    })
    .join("");
  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img">${layers}</svg>`;
}

function badge(status) {
  const kind = status === "ready" || status === "ok" || status === "approved" ? "ok" : status === "blocked" || status === "rejected" ? "bad" : "warn";
  return `<span class="badge ${kind}">${esc(status)}</span>`;
}

async function refreshEnterprise() {
  const data = await api("/api/enterprise");
  state.enterprise = data;
  renderEnterpriseSwitch(data);
  renderEnterpriseComponents(data.registry, data.profiles);
  renderEnterpriseProfiles(data.profiles);
  renderEnterpriseFde(data.fde);
}

function renderEnterpriseSwitch(data) {
  const rows = data.switch.rows
    .map(
      (row) =>
        `<tr><td>${esc(row.industry)}</td><td class="mono">${esc(row.profile_id)}</td><td>${esc(row.enterprise)}</td><td>${row.components_enabled}</td><td>${row.capabilities}</td><td>${esc(row.deployment || "-")}</td><td>${esc((row.languages || []).join(", "))}</td><td>${badge(row.status)}</td></tr>`
    )
    .join("");
  const specific = Object.entries(data.switch.capabilities_industry_specific)
    .map(([industry, capabilities]) => `<li><strong>${esc(industry)}</strong>: ${esc(capabilities.join(", ") || "-")}</li>`)
    .join("");
  $("#ent-switch").innerHTML =
    `<table><thead><tr><th>${esc(t("workstation.industry"))}</th><th>profile</th><th>enterprise</th><th>${esc(t("enterprise.components"))}</th><th>${esc(t("enterprise.capabilities"))}</th><th>deployment</th><th>${esc(t("common.language"))}</th><th>status</th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="hint">${esc(data.switch.proof.note)}</p>` +
    `<p class="hint">shared capabilities: ${data.switch.capabilities_shared.length}</p><ul class="plain">${specific}</ul>`;
}

function renderEnterpriseComponents(registry, profiles) {
  const rows = registry.components
    .map(
      (component) =>
        `<tr><td class="mono">${esc(component.component_id)}</td><td>${esc(component.kind)}</td><td>${esc((component.industries || []).join(", "))}</td><td>${component.capabilities.length}</td><td>${esc(component.maturity)}</td></tr>`
    )
    .join("");
  const counts = profiles.map((profile) => `${profile.profile_id}: ${profile.assembly.components_enabled}/${profile.assembly.components_available}`).join(" · ");
  $("#ent-components").innerHTML =
    `<table><thead><tr><th>component</th><th>kind</th><th>industries</th><th>${esc(t("enterprise.capabilities"))}</th><th>maturity</th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="hint">registry ${esc(registry.version)} · ${registry.components.length} components · enabled per profile: ${esc(counts)}</p>`;
}

function renderEnterpriseProfiles(profiles) {
  $("#ent-profile").innerHTML = profiles
    .map((profile) => {
      const enterprise = profile.enterprise;
      const assembly = profile.assembly;
      const deployment = profile.deployment || {};
      const locale = profile.locale || {};
      const growth = profile.growth || {};
      const issues = assembly.issues.length
        ? `<ul class="plain">${assembly.issues.map((issue) => `<li>${esc(issue.component_id)}: ${esc(issue.detail)}</li>`).join("")}</ul>`
        : `<p class="hint">${esc(t("enterprise.no_issues"))}</p>`;
      return (
        `<div class="rule-row"><div class="head"><strong>${esc(profile.profile_id)} · ${esc(enterprise.name)}</strong>${badge(assembly.status)}</div>` +
        `<p class="hint">${esc(enterprise.industry)} · ${esc(enterprise.size)} · ${esc(enterprise.region)} · ${esc(deployment.mode || "-")} · ${esc(locale.primary || "-")} + ${esc((locale.secondary || []).join(", "))}</p>` +
        `<p class="hint">${assembly.components_enabled} components · ${assembly.capabilities.length} ${esc(t("enterprise.capabilities"))} · ${assembly.contracts.length} contracts · site ${esc(growth.site_id || "-")}</p>` +
        issues +
        `</div>`
      );
    })
    .join("");
}

function renderEnterpriseFde(fde) {
  if (!fde) {
    $("#ent-fde").innerHTML = `<p class="hint">-</p>`;
    return;
  }
  const phases = fde.phases
    .map((phase) => `<tr><td>${esc(phase.phase_id)}</td><td>${esc(phase.title[state.lang] || phase.title.en)}</td><td>${phase.done}/${phase.total}</td></tr>`)
    .join("");
  const blocking = fde.blocking_open.length
    ? `<ul class="plain">${fde.blocking_open.map((item) => `<li>${esc(item.item_id)} · ${esc(item.title[state.lang] || item.title.en)} (${esc(item.owner)})</li>`).join("")}</ul>`
    : `<p class="hint">no blocking item</p>`;
  const percent = (fde.readiness_bp / 100).toFixed(0);
  $("#ent-fde").innerHTML =
    `<p><strong>${percent}%</strong> · ${fde.items_done}/${fde.items_total} items done · ${badge(fde.status)}</p>` +
    `<div class="split-bar"><span style="width:${percent}%;background:var(--ok)"></span></div>` +
    `<table><thead><tr><th>phase</th><th>title</th><th>done</th></tr></thead><tbody>${phases}</tbody></table>` +
    `<p class="hint">${fde.blocking_open.length} ${esc(t("enterprise.blocking"))}</p>${blocking}`;
}

/* -- growth stack -------------------------------------------------------- */
async function refreshSite() {
  const data = await api("/api/growth/site");
  const site = data.site;
  state.site = site;
  $("#ent-seo-score").textContent = `${t("enterprise.seo")} ${(site.seo.score_bp / 100).toFixed(1)}`;
  const rows = site.pages
    .map(
      (page) =>
        `<tr><td><a href="${esc(page.path)}" target="_blank" rel="noopener" class="mono">${esc(page.path)}</a></td><td>${esc(page.language)}</td><td>${esc(page.title)}</td><td>${page.hreflang.length}</td><td>${esc(page.status)}</td></tr>`
    )
    .join("");
  const issues = site.seo.issues.length
    ? `<ul class="plain">${site.seo.issues.map((issue) => `<li>${esc(issue.code)} · ${esc(issue.page_id)} · ${esc(issue.severity)} · ${esc(issue.detail)}</li>`).join("")}</ul>`
    : `<p class="hint">no SEO issue: every page passes the declared bounds</p>`;
  const inquiry = site.inquiry_form;
  $("#ent-site").innerHTML =
    `<p class="hint">${esc(site.site_id)} · ${site.languages.length} languages · ${site.pages.length} ${esc(t("enterprise.pages"))} · profile ${esc(site.profile_id)}</p>` +
    `<table><thead><tr><th>path</th><th>${esc(t("common.language"))}</th><th>title</th><th>hreflang</th><th>status</th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="hint">SEO rules: title ${site.seo.rules.title_min}-${site.seo.rules.title_max} · description ${site.seo.rules.description_min}-${site.seo.rules.description_max}</p>` +
    issues +
    `<p class="hint">inquiry form ${esc(inquiry.form_id)} -> ${esc(inquiry.endpoint)}</p>`;
}

async function refreshCrm() {
  const data = await api("/api/growth/crm");
  state.crm = data;
  const stages = data.stages.map((row) => row.stage);
  const columns = data.stages
    .map((column) => {
      const index = stages.indexOf(column.stage);
      const next = index >= 0 && index + 1 < stages.length ? stages[index + 1] : null;
      const cards = column.leads
        .map((lead) => {
          const forward =
            next && !["won", "lost"].includes(column.stage)
              ? `<button data-action="crm-advance" data-inquiry="${esc(lead.inquiry_id)}" data-stage="${esc(next)}" data-note="moving the lead forward after the desk follow-up">${esc(next)}</button>`
              : "";
          const close =
            !["won", "lost"].includes(column.stage)
              ? `<button class="danger" data-action="crm-advance" data-inquiry="${esc(lead.inquiry_id)}" data-stage="lost" data-note="no order this season, closing the lead">lost</button>`
              : "";
          const quote = lead.quote
            ? `<span class="chip">${esc(lead.quote.quote_id)} ${(lead.quote.amount_cents / 100).toFixed(0)} ${esc(lead.quote.currency)}</span>`
            : "";
          return `<div class="lead"><div class="head"><strong class="mono">${esc(lead.lead_id)}</strong><span>${lead.score}</span></div><p class="hint">${esc(lead.language)} · ${esc(lead.intent)} · ${esc(lead.owner)}</p>${quote}<div class="actions">${forward}${close}</div></div>`;
        })
        .join("");
      return `<div class="stage-col"><h3>${esc(column.stage)} · ${column.count}</h3>${cards || `<p class="hint">-</p>`}</div>`;
    })
    .join("");
  $("#crm-board").innerHTML =
    `<div class="crm">${columns}</div>` +
    `<p class="hint">SLA breaches: ${data.sla_breaches.length} · open follow-ups: ${data.open_follow_ups.length}</p>`;
}

async function submitInquiry(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    language: state.lang,
    contact: {
      name: form.contact_name.value,
      email: form.email.value,
      company: form.company.value,
      country: form.country.value.toUpperCase(),
      channel: "site_form",
    },
    message: form.message.value,
    intent: form.intent.value,
    product_interest: ["custom jewellery"],
  };
  try {
    const data = await api("/api/growth/inquiry", { method: "POST", body: JSON.stringify(payload) });
    const inquiry = data.inquiry;
    $("#inq-result").innerHTML =
      `<p class="hint">${esc(t("enterprise.inquiry_ok"))} <strong class="mono">${esc(inquiry.inquiry_id)}</strong> · ${esc(t("common.owner"))} ${esc(inquiry.lead.owner.name)} · ${esc(t("common.score"))} ${inquiry.lead.score}</p>`;
    toast(`${inquiry.inquiry_id} -> ${inquiry.lead.owner.name}`, "ok");
    await refreshCrm();
  } catch (error) {
    toast(`${t("common.error")}: ${error.message}`);
  }
}

/* -- cultural IP studio -------------------------------------------------- */
async function refreshIp() {
  const data = await api("/api/ip");
  state.ip = data;
  const assets = data.assets.reduce((map, asset) => {
    map[asset.asset_id] = asset;
    return map;
  }, {});
  renderBible(data.bible);
  renderAssets(data.asset_summary, data.assets);
  renderDrama(data.drama, assets);
  renderLicensing(data.license, data.merch_specs, data.reviews);
}

function renderBible(bible) {
  const world = bible.world;
  const rules = world.rules.map((rule) => `<li>${esc(rule)}</li>`).join("");
  const characters = bible.canon.characters
    .map((character) => {
      const arcs = character.story_arc.map((beat) => `<li><strong>${esc(beat.beat)}</strong>: ${esc(beat.summary)}</li>`).join("");
      return (
        `<div class="rule-row"><div class="head"><strong>${esc(character.name[state.lang] || character.name.en)}</strong><span class="mono">${esc(character.character_id)}</span></div>` +
        `<p class="hint">${esc(character.role)} · ${esc(character.element)} · ${esc(character.archetype)}</p>` +
        swatches(character.palette) +
        `<p class="hint">${esc(t("ip.motifs"))}: ${esc(character.motifs.join(", "))}</p>` +
        `<p class="hint">${esc(t("ip.taboos"))}: ${esc(character.taboos.join("; "))}</p>` +
        `<p class="hint">"${esc(character.voice.signature_line)}"</p>` +
        `<p class="hint">${esc(t("ip.arc"))}:</p><ul class="plain">${arcs}</ul></div>`
      );
    })
    .join("");
  $("#ip-bible").innerHTML =
    `<p class="hint">${esc(bible.title[state.lang] || bible.title.en)} · ${esc(world.era)} · ${esc(world.premise)}</p>` +
    `<p class="hint">${esc(t("ip.world_rules"))}:</p><ul class="plain">${rules}</ul>` +
    characters;
}

function renderAssets(summary, assets) {
  const kinds = Object.entries(summary.by_kind)
    .map(([kind, count]) => `${kind} ${count}`)
    .join(" · ");
  $("#ip-assets").innerHTML =
    `<p class="hint">${assets.length} ${esc(t("ip.asset_count"))} · ${esc(kinds)} · ${summary.ai_assisted} AI assisted · checksum recomputes</p>` +
    assets
      .map(
        (asset) =>
          `<figure class="asset-card"><div class="asset-art">${assetSvg(asset)}</div><figcaption><strong class="mono">${esc(asset.asset_id)}</strong><span class="hint">${esc(asset.kind)} · ${esc(asset.view_or_name)}</span><span class="hint mono">${esc(asset.checksum.slice(0, 12))}</span></figcaption></figure>`
      )
      .join("");
}

function renderDrama(drama, assets) {
  const frames = drama.storyboard.frames
    .map((frame) => {
      const asset = assets[frame.asset_ids[0]];
      return `<figure class="frame-card">${asset ? assetSvg(asset) : ""}<figcaption><strong>${esc(frame.frame_id)}</strong><span class="hint">${esc(frame.scene_id)} · ${esc(frame.shot)}/${esc(frame.camera)} · ${frame.duration_seconds}s</span></figcaption></figure>`;
    })
    .join("");
  const edl = drama.cut.edl
    .map((row) => `<tr><td>${row.order}</td><td class="mono">${esc(row.frame_id)}</td><td>${esc(row.in_tc)}</td><td>${esc(row.out_tc)}</td><td>${esc(row.transition)}</td></tr>`)
    .join("");
  $("#ip-drama-chip").textContent = `${drama.cut.total_seconds}s · ${drama.storyboard.frames.length} frames · ${drama.subtitles.lines.length} subtitles · ${drama.review.status}`;
  $("#ip-frames").innerHTML = frames;
  $("#ip-drama").innerHTML =
    `<p class="hint">${esc(drama.title[state.lang] || drama.title.en)} · ${esc(drama.genre)} · bible ${esc(drama.bible_ref)} · review ${esc(drama.review.content_review_ref)}</p>` +
    `<p class="hint">${esc(drama.logline)}</p>` +
    `<p class="hint">${esc(t("ip.subtitles"))}: ${drama.subtitles.lines.length} · ${esc(drama.subtitles.language)} · ${esc(drama.review.authenticity_label)}</p>` +
    `<table><thead><tr><th>#</th><th>frame</th><th>in</th><th>out</th><th>transition</th></tr></thead><tbody>${edl}</tbody></table>`;
}

function renderLicensing(license, merchSpecs, reviews) {
  const documents = license.documents
    .map(
      (document) =>
        `<tr><td class="mono">${esc(document.document_id)}</td><td>${esc(document.kind)}</td><td>${badge(document.status === "signed" ? "approved" : document.status)}</td><td>${esc(document.derivative_categories.join(", "))}</td><td>${document.signatories.length}</td><td class="mono">${esc(document.checksum.slice(0, 10))}</td></tr>`
    )
    .join("");
  const merch = merchSpecs
    .map(
      (spec) =>
        `<tr><td class="mono">${esc(spec.spec_id)}</td><td>${esc(spec.category)}</td><td>${esc(spec.character_ids.join(", "))}</td><td>${spec.quality.sampling.aql}</td><td>${(spec.rights.royalty_rate_bp / 100).toFixed(1)}%</td><td>${esc(spec.content_review_ref)}</td></tr>`
    )
    .join("");
  const reviewsBySubject = reviews
    .map(
      (review) =>
        `<tr><td class="mono">${esc(review.review_id)}</td><td>${esc(review.subject.kind)}</td><td class="mono">${esc(review.subject.ref)}</td><td>${badge(review.verdict)}</td><td>${review.checklist.length}</td><td>${esc(review.reviewer.role)}</td></tr>`
    )
    .join("");
  $("#ip-license").innerHTML =
    `<p class="hint">${esc(license.license_id)} · royalty ${(license.usage.royalty_rate_bp / 100).toFixed(1)}% · ${license.usage.term_months} months · exclusivity ${license.usage.exclusivity}</p>` +
    `<table><thead><tr><th>document</th><th>kind</th><th>${esc(t("ip.status"))}</th><th>categories</th><th>signatories</th><th>checksum</th></tr></thead><tbody>${documents}</tbody></table>` +
    `<p class="hint">${esc(license.content_review.authenticity_label)}</p>`;
  $("#ip-merch").innerHTML =
    `<table><thead><tr><th>spec</th><th>category</th><th>characters</th><th>${esc(t("ip.aql"))}</th><th>${esc(t("ip.royalty"))}</th><th>review</th></tr></thead><tbody>${merch}</tbody></table>` +
    `<p class="hint">${merchSpecs.length} specifications cover ${new Set(merchSpecs.map((spec) => spec.category)).size} derivative categories.</p>`;
  $("#ip-reviews").innerHTML = `<table><thead><tr><th>review</th><th>subject</th><th>ref</th><th>verdict</th><th>checklist</th><th>role</th></tr></thead><tbody>${reviewsBySubject}</tbody></table>`;
}

async function handleAction(action, node) {
  switch (action) {
    case "ws-assess":
      await assessConcept(node.dataset.concept);
      break;
    case "ws-series":
      await expandSeries(node.dataset.concept);
      break;
    case "ws-order":
      try {
        await api("/api/orders", { method: "POST", body: JSON.stringify({ concept_id: node.dataset.concept }) });
        await refreshOrders();
        $$("#tabs .tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === "presale"));
        $$(".panel").forEach((panel) => panel.classList.toggle("is-active", panel.id === "panel-presale"));
        toast("order created", "ok");
      } catch (error) {
        toast(`${t("common.error")}: ${error.message}`);
      }
      break;
    case "ws-render":
      await renderConceptImage(node.dataset.concept);
      break;
    case "ws-copy":
      await renderConceptCopy(node.dataset.concept);
      break;
    case "order-select":
      await showOrder(node.dataset.order);
      break;
    case "order-advance":
      await advanceOrder(node.dataset.order, node.dataset.event, node.dataset.actor);
      break;
    case "refund-request":
      await refundAction(node.dataset.order, "request");
      break;
    case "refund-approve":
      await refundAction(node.dataset.order, "approve");
      break;
    case "refund-execute":
      await refundAction(node.dataset.order, "execute");
      break;
    case "dispute-open":
      await disputeAction(node.dataset.order, "open");
      break;
    case "dispute-resolve":
      await disputeAction(node.dataset.order, "resolve");
      break;
    case "review-decide":
      await decideReview(node.dataset.queue);
      break;
    case "edition-issue":
      await issueEdition(node.dataset.edition);
      break;
    case "collector-transfer":
      await transferCollector(node.dataset.record);
      break;
    case "rule-explain":
      await explainRule(node.dataset.rule);
      break;
    case "dispatch-select":
      toast("select the work order panel below", "ok");
      break;
    case "crm-advance":
      try {
        await api(`/api/growth/inquiries/${node.dataset.inquiry}/advance`, {
          method: "POST",
          body: JSON.stringify({ stage: node.dataset.stage, note: node.dataset.note }),
        });
        await refreshCrm();
        toast(`${node.dataset.inquiry} -> ${node.dataset.stage}`, "ok");
      } catch (error) {
        toast(`${t("common.error")}: ${error.message}`);
      }
      break;
    default:
      break;
  }
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const node = event.target.closest("[data-action]");
    if (!node) return;
    event.preventDefault();
    handleAction(node.dataset.action, node);
  });
  $("#ws-generate").addEventListener("click", generateConcepts);
  $("#lib-search").addEventListener("click", runLibrarySearch);
  $("#lib-load-sample").addEventListener("click", loadRejectionSample);
  $("#lib-ingest").addEventListener("click", ingestAsset);
  $("#custom-preview").addEventListener("click", previewCustomization);
  $("#custom-create").addEventListener("click", createCustomOrder);
  $("#ent-refresh-site").addEventListener("click", async () => {
    try {
      await refreshSite();
      await refreshCrm();
      toast("site refreshed", "ok");
    } catch (error) {
      toast(`${t("common.error")}: ${error.message}`);
    }
  });
  $("#inq-form").addEventListener("submit", submitInquiry);
  $("#edition-create").addEventListener("click", createEdition);
  $("#order-create").addEventListener("click", async () => {
    try {
      const data = await api("/api/orders", {
        method: "POST",
        body: JSON.stringify({
          concept_id: $("#order-concept").value,
          model: $("#order-model").value,
        }),
      });
      state.selectedOrder = data.order.order_id;
      await refreshOrders();
      await showOrder(data.order.order_id);
      toast(`order ${data.order.order_id} created`, "ok");
    } catch (error) {
      toast(`${t("common.error")}: ${error.message}`);
    }
  });
  $("#lang").addEventListener("change", async (event) => {
    state.lang = event.target.value;
    applyI18n();
    renderChrome();
    fillSelects();
    fillConceptSelect();
    fillCustomization();
    renderReference();
    $("#ws-concepts").innerHTML = state.lastConcepts.map(conceptCard).join("");
    await refreshRules();
    renderOrderList();
    if (state.selectedOrder) await showOrder(state.selectedOrder);
    await refreshDispatch();
    await refreshEditions();
    await refreshCapacity();
    await refreshQuality();
    await refreshModelStatus();
  });
  $("#ws-image").addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    try {
      const bitmap = await createImageBitmap(file);
      const canvas = document.createElement("canvas");
      canvas.width = 40;
      canvas.height = 40;
      const context = canvas.getContext("2d");
      context.drawImage(bitmap, 0, 0, 40, 40);
      const pixels = context.getImageData(0, 0, 40, 40).data;
      const buckets = new Map();
      for (let index = 0; index < pixels.length; index += 4) {
        const r = pixels[index];
        const g = pixels[index + 1];
        const b = pixels[index + 2];
        const alpha = pixels[index + 3];
        if (alpha < 128) continue;
        const key = `${r >> 5}-${g >> 5}-${b >> 5}`;
        const entry = buckets.get(key) || { r: 0, g: 0, b: 0, n: 0 };
        entry.r += r;
        entry.g += g;
        entry.b += b;
        entry.n += 1;
        buckets.set(key, entry);
      }
      const colors = Array.from(buckets.values())
        .sort((left, right) => right.n - left.n)
        .slice(0, 6)
        .map(
          (entry) =>
            `#${[entry.r / entry.n, entry.g / entry.n, entry.b / entry.n]
              .map((value) => Math.round(value).toString(16).padStart(2, "0"))
              .join("")
              .toUpperCase()}`
        );
      state.referencePalette = colors;
      renderReference();
      toast(`palette extracted: ${colors.length} colours`, "ok");
    } catch (error) {
      toast(`could not read the image: ${error.message}`);
    }
  });
}

async function init() {
  try {
    state.spec = await api("/api/spec");
    state.i18n = (await api("/api/i18n")).strings;
    const industries = await api("/api/industries");
    state.industries = industries.industries;
    state.styles = industries.styles || [];
    state.concepts = (await api("/api/concepts")).concepts;
  } catch (error) {
    document.body.innerHTML = `<pre class="code">Cannot reach the API: ${esc(error.message)}\nStart the server with: python -m c2m_craft serve</pre>`;
    return;
  }
  $("#ws-text").value =
    "a coastal heritage pendant series for duty free retail, interlace and fret motifs";
  bindTabs();
  bindEvents();
  applyI18n();
  renderChrome();
  fillSelects();
  fillConceptSelect();
  fillCustomization();
  renderContracts();
  await refreshRules();
  await refreshOrders();
  await refreshDispatch();
  await refreshReviewQueue();
  await refreshEditions();
  await refreshCapacity();
  await refreshQuality();
  await refreshModelStatus();
  await runLibrarySearch();
  loadRejectionSample();
}

document.addEventListener("DOMContentLoaded", init);
