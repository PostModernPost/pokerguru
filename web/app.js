// Preflop drill front end. Plain JavaScript, no build step.
"use strict";

const $ = (id) => document.getElementById(id);
const SUITS = { s: "♠", h: "♥", d: "♦", c: "♣" };
const TABLE_LABELS = { 6: "6-max", 9: "9-handed" };
const GRADE_TEXT = { correct: "Correct", acceptable: "Acceptable (mixed)", wrong: "Wrong" };
const KIND_COLORS = { allin: "var(--allin)", raise: "var(--raise)", call: "var(--call)", fold: "var(--fold)" };
const KIND_ORDER = ["allin", "raise", "call", "fold"]; // aggressive first in the range grid
const FILTER_KEY = "pokerguru.preflopFilters";

let options = null;
let filters = { table_sizes: [], hero_positions: [], spot_types: [] };
let current = null; // the spot on screen
let shownAt = 0;
let busy = false;

// ---------- helpers ----------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

function num(x) {
  return String(+Number(x).toFixed(2));
}

function actionKind(id) {
  if (id === "fold") return "fold";
  if (id === "call") return "call";
  if (id === "allin") return "allin";
  if (id.startsWith("raise")) return "raise";
  return "fold";
}

function show(screen) {
  for (const s of ["filters-screen", "drill-screen", "result-screen", "message-screen"]) {
    $(s).hidden = s !== screen;
  }
  window.scrollTo(0, 0);
}

function showMessage(text) {
  $("message").textContent = text;
  show("message-screen");
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `Server error ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

function renderCard(code) {
  const rank = code[0] === "T" ? "10" : code[0];
  const suit = code[1];
  return el("div", { class: `card s-${suit}`, "aria-label": code },
    el("span", { class: "r" }, rank),
    el("span", { class: "s" }, SUITS[suit] || suit));
}

function setSampleWarning(on) {
  $("sample-warning").hidden = !on;
}

function updateScore(summary) {
  if (!summary) return;
  $("score").textContent = summary.total
    ? `${summary.correct}/${summary.total} correct`
    : "No hands yet";
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

function availablePositions() {
  const sizes = filters.table_sizes.length ? filters.table_sizes : options.table_sizes;
  const order = ["UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
  const have = new Set(sizes.flatMap((s) => options.positions[s] || []));
  return order.filter((p) => have.has(p));
}

function chip(label, pressed, onClick) {
  return el("button", { class: "chip", "aria-pressed": String(pressed), type: "button", onclick: onClick }, label);
}

function toggle(list, value) {
  const i = list.indexOf(value);
  if (i >= 0) list.splice(i, 1); else list.push(value);
}

function renderFilters() {
  const t = $("f-table"); t.replaceChildren();
  for (const size of options.table_sizes) {
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
  const s = $("f-spot"); s.replaceChildren();
  for (const st of options.spot_types) {
    s.append(chip(st.label, filters.spot_types.includes(st.id), () => {
      toggle(filters.spot_types, st.id); renderFilters();
    }));
  }
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
  const avail = new Set(availablePositions());
  filters.table_sizes = filters.table_sizes.filter((s) => options.table_sizes.includes(s));
  filters.hero_positions = filters.hero_positions.filter((p) => avail.has(p));
  filters.spot_types = filters.spot_types.filter((s) => options.spot_types.some((o) => o.id === s));
  nextSpot();
})();
