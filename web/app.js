// Preflop drill front end. Plain JavaScript, no build step. Shared helpers are in common.js.
"use strict";

const TABLE_LABELS = { 2: "Heads-up", 6: "6-max", 9: "9-handed" };
const GRADE_TEXT = { correct: "Correct", acceptable: "Acceptable (mixed)", wrong: "Wrong" };
const KIND_COLORS = { allin: "var(--allin)", raise: "var(--raise)", call: "var(--call)", fold: "var(--fold)" };
const KIND_ORDER = ["allin", "raise", "call", "fold"]; // aggressive first in the range grid
const FILTER_KEY = "pokerguru.preflopFilters";

let options = null;
let filters = { formats: [], table_sizes: [], hero_positions: [], spot_types: [], stacks: [], leaks_only: false };
let current = null; // the spot on screen
let shownAt = 0;
let busy = false;

// ---------- helpers ----------

function actionKind(id) {
  if (id === "fold") return "fold";
  if (id === "call") return "call";
  if (id === "allin") return "allin";
  if (id.startsWith("raise")) return "raise";
  return "fold";
}

// ---------- filters ----------

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(FILTER_KEY) || "null");
    if (saved) filters = { ...filters, ...saved };
  } catch (_) { /* storage unavailable: use defaults */ }
}

function saveFilters() {
  try { localStorage.setItem(FILTER_KEY, JSON.stringify(filters)); } catch (_) { /* ignore */ }
}

// What the selected formats offer (all formats when none is selected).
function offered(key) {
  const fmts = filters.formats.length ? filters.formats : Object.keys(options.per_format);
  const out = new Set();
  for (const f of fmts) for (const v of (options.per_format[f] || {})[key] || []) out.add(v);
  return [...out].sort((a, b) => a - b);
}

function availablePositions() {
  const sizes = filters.table_sizes.length ? filters.table_sizes : offered("table_sizes");
  const order = ["UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
  const have = new Set(sizes.flatMap((s) => options.positions[s] || []));
  return order.filter((p) => have.has(p));
}

function pruneFilters() {
  const sizes = new Set(offered("table_sizes")), stacks = new Set(offered("stacks")), spots = new Set(offered("spot_types"));
  filters.table_sizes = filters.table_sizes.filter((s) => sizes.has(s));
  filters.stacks = filters.stacks.filter((s) => stacks.has(s));
  filters.spot_types = filters.spot_types.filter((s) => spots.has(s));
  const avail = new Set(availablePositions());
  filters.hero_positions = filters.hero_positions.filter((p) => avail.has(p));
}

function renderFilters() {
  const f = $("f-format"); f.replaceChildren();
  for (const o of options.formats) {
    f.append(chip(o.label, filters.formats.includes(o.id), () => {
      toggle(filters.formats, o.id); pruneFilters(); renderFilters();
    }));
  }
  const t = $("f-table"); t.replaceChildren();
  for (const size of offered("table_sizes")) {
    t.append(chip(TABLE_LABELS[size] || `${size}-handed`, filters.table_sizes.includes(size), () => {
      toggle(filters.table_sizes, size);
      const avail = new Set(availablePositions());
      filters.hero_positions = filters.hero_positions.filter((p) => avail.has(p));
      renderFilters();
    }));
  }
  const p = $("f-pos"); p.replaceChildren();
  for (const pos of availablePositions()) {
    p.append(chip(pos, filters.hero_positions.includes(pos), () => {
      toggle(filters.hero_positions, pos); renderFilters();
    }));
  }
  const k = $("f-stack"); k.replaceChildren();
  for (const stack of offered("stacks")) {
    k.append(chip(`${stack}bb`, filters.stacks.includes(stack), () => {
      toggle(filters.stacks, stack); renderFilters();
    }));
  }
  const s = $("f-spot"); s.replaceChildren();
  const spotIds = new Set(offered("spot_types"));
  for (const st of options.spot_types.filter((o) => spotIds.has(o.id))) {
    s.append(chip(st.label, filters.spot_types.includes(st.id), () => {
      toggle(filters.spot_types, st.id); renderFilters();
    }));
  }
  const m = $("f-mode"); m.replaceChildren(
    chip("Everything", !filters.leaks_only, () => { filters.leaks_only = false; renderFilters(); }),
    chip("Drill my leaks", filters.leaks_only, () => { filters.leaks_only = true; renderFilters(); }),
  );
  $("leak-hint").textContent = filters.leaks_only
    ? "Only positions, spot types and hand categories you score under 70% on, plus spots you missed that are due again. Needs a few hands of history first."
    : "Missed spots come back sooner and weak areas come up more often either way. See the Stats tab.";
  $("filters-error").hidden = true;
}

function openFilters() {
  renderFilters();
  show("filters-screen");
}

// ---------- drill ----------

async function nextSpot() {
  if (busy) return;
  busy = true;
  try {
    current = await api("/api/preflop/next", filters);
    renderSpot(current);
    show("drill-screen");
    shownAt = performance.now();
  } catch (e) {
    if (!$("filters-screen").hidden) {
      $("filters-error").textContent = e.message;
      $("filters-error").hidden = false;
    } else {
      showMessage(e.message);
    }
  } finally {
    busy = false;
  }
}

function seatStatus(seat) {
  if (seat.status === "hero") return "You";
  if (seat.status === "fold") return "fold";
  if (seat.status === "raise") return seat.to_bb != null ? `${num(seat.to_bb)}bb` : "raise";
  if (seat.blind != null) return `${num(seat.blind)}bb`;
  return "–";
}

function renderSpot(spot) {
  setSampleWarning(spot.is_sample);

  const tags = $("spot-tags"); tags.replaceChildren(
    el("span", { class: "tag" }, TABLE_LABELS[spot.table_size] || `${spot.table_size}-handed`),
    el("span", { class: "tag" }, `${num(spot.stack_bb)}bb deep`),
    el("span", { class: "tag" }, spot.format === "cash" ? "Cash" : "Tournament"),
    el("span", { class: "tag strong" }, spot.spot_label),
  );
  if (spot.reason === "review") tags.append(el("span", { class: "tag review" }, "Review: you missed this before"));
  else if (filters.leaks_only) tags.append(el("span", { class: "tag review" }, "Leak drill"));

  const seats = $("seats"); seats.replaceChildren();
  for (const seat of spot.seats) {
    seats.append(el("div", { class: `seat ${seat.status}` },
      el("span", { class: "pos" }, seat.pos),
      el("span", { class: "st" }, seatStatus(seat))));
  }

  const hist = $("history"); hist.replaceChildren();
  if (!spot.history.length) {
    hist.append(el("li", {}, "You're first to act"));
  } else if (spot.history.every((h) => h.action === "fold")) {
    hist.append(el("li", {}, "Folded to you"));
  } else {
    for (const h of spot.history) {
      if (h.action === "fold" && !h.is_hero) continue; // folds are shown on the seats
      hist.append(el("li", { class: h.action }, h.text));
    }
  }

  const pot = $("pot-line"); pot.replaceChildren();
  if (spot.pot_bb != null) {
    pot.append("Pot ", el("b", {}, `${num(spot.pot_bb)}bb`));
    if (spot.to_call_bb > 0 && spot.spot_type !== "rfi") {
      pot.append(" · To call ", el("b", {}, `${num(spot.to_call_bb)}bb`));
    }
  } else {
    pot.append("Bet sizes not given in this chart");
  }

  $("hero-label").textContent = spot.hero_pos;
  $("hero-cards").replaceChildren(...spot.hero_cards.map(renderCard));

  const actions = $("actions"); actions.replaceChildren();
  spot.actions.forEach((a, i) => {
    actions.append(el("button", {
      class: `action-btn k-${actionKind(a.id)}`, type: "button", "data-key": String(i + 1),
      onclick: () => answer(a.id),
    }, a.label));
  });
}

async function answer(actionId) {
  if (busy || !current) return;
  busy = true;
  const elapsed = Math.round(performance.now() - shownAt);
  for (const b of document.querySelectorAll(".action-btn")) b.disabled = true;
  try {
    const result = await api("/api/preflop/answer", {
      chart_id: current.chart_id,
      hero_cards: current.hero_cards,
      action: actionId,
      response_time_ms: elapsed,
    });
    renderResult(current, result);
    show("result-screen");
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

// ---------- result ----------

function gradientFor(freqs, actions) {
  // freqs: list aligned with actions. Returns a left-to-right stacked colour bar.
  const parts = actions
    .map((a, i) => ({ kind: actionKind(a.id), f: freqs[i] }))
    .filter((p) => p.f > 0)
    .sort((x, y) => KIND_ORDER.indexOf(x.kind) - KIND_ORDER.indexOf(y.kind));
  if (parts.length === 1) return KIND_COLORS[parts[0].kind];
  let at = 0;
  const stops = [];
  for (const p of parts) {
    const end = at + p.f * 100;
    stops.push(`${KIND_COLORS[p.kind]} ${at}% ${end}%`);
    at = end;
  }
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

function renderResult(spot, r) {
  setSampleWarning(r.is_sample);
  updateScore(r.summary);

  const banner = $("grade-banner");
  banner.className = `grade-banner ${r.grade}`;
  banner.textContent = GRADE_TEXT[r.grade] || r.grade;

  $("result-cards").replaceChildren(...r.hero_cards.map(renderCard));
  const vs = spot.villain_pos ? ` vs ${spot.villain_pos}` : "";
  $("result-spot").textContent = `${spot.hero_pos}${vs} · ${spot.spot_label} · ${r.hand_class}`;
  let chose = `You chose ${r.chosen_label} (chart: ${r.chosen_pct})`;
  if (r.grade !== "correct") chose += `. Most often: ${r.best_actions.join(" / ")}`;
  $("you-chose").textContent = chose;

  const freqs = $("freqs"); freqs.replaceChildren();
  for (const f of r.frequencies) {
    freqs.append(el("div", { class: `freq-row${f.id === r.chosen_action ? " chosen" : ""}` },
      el("span", { class: "label" }, f.label),
      el("div", { class: "bar" }, el("i", { style: `width:${f.freq * 100}%;background:${KIND_COLORS[actionKind(f.id)]}` })),
      el("span", { class: "pct" }, f.pct)));
  }
  $("explanation").textContent = r.explanation;

  const legend = $("legend"); legend.replaceChildren();
  for (const a of r.actions) {
    legend.append(el("span", { style: `--c:${KIND_COLORS[actionKind(a.id)]}` }, a.label));
  }

  const grid = $("range-grid"); grid.replaceChildren();
  for (const row of r.grid) {
    for (const hand of row) {
      const cell = el("div", {
        class: `cell${hand === r.hand_class ? " hero" : ""}`,
        title: hand + ": " + r.actions.map((a, i) => `${a.label} ${Math.round(r.range[hand][i] * 100)}%`).join(", "),
        style: `background:${gradientFor(r.range[hand], r.actions)}`,
      }, hand);
      grid.append(cell);
    }
  }

  const src = $("source"); src.replaceChildren();
  const name = r.source.name || "unknown";
  src.append("Chart source: ", el("span", { class: r.is_sample ? "fake" : "" }, name));
  if (r.source.url) src.append(" · ", el("a", { href: r.source.url, target: "_blank", rel: "noopener" }, "link"));
  if (r.source.notes) src.append(el("br"), r.source.notes);
}

// ---------- startup ----------

document.addEventListener("keydown", (e) => {
  if (!$("drill-screen").hidden && /^[1-9]$/.test(e.key)) {
    const btn = document.querySelector(`.action-btn[data-key="${e.key}"]`);
    if (btn) btn.click();
  } else if (!$("result-screen").hidden && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    nextSpot();
  }
});

$("filters-btn").addEventListener("click", openFilters);
$("start-btn").addEventListener("click", () => { saveFilters(); nextSpot(); });
$("next-btn").addEventListener("click", nextSpot);

(async function init() {
  try {
    options = await api("/api/options");
    updateScore(await api("/api/summary"));
  } catch (e) {
    showMessage("Can't reach the trainer server: " + e.message);
    return;
  }
  if (!options.chart_count) {
    showMessage("No charts found in data/charts. Add chart files and restart the server.");
    return;
  }
  setSampleWarning(options.sample_in_use);
  loadFilters();
  // Drop saved choices that no longer exist (e.g. charts were removed).
  filters.formats = (filters.formats || []).filter((f) => options.per_format[f]);
  filters.stacks = filters.stacks || [];
  filters.leaks_only = Boolean(filters.leaks_only);
  pruneFilters();
  nextSpot();
})();
