// Equity and pot odds drill. Shared helpers are in common.js.
"use strict";

const GRADE_WORDS = { correct: "Correct", acceptable: "Close enough", wrong: "Wrong" };
const FILTER_KEY = "pokerguru.equityFilters";
const SCORE_DRILL = "pot_odds_decision";

let options = null;
let filters = { games: [], streets: [] };
let current = null;
let chosen = { bucket: null, decision: null };
let shownAt = 0;
let busy = false;

// ---------- filters ----------

function renderFilters() {
  const g = $("f-game"); g.replaceChildren();
  for (const o of options.games) {
    g.append(chip(o.label, filters.games.includes(o.id), () => { toggle(filters.games, o.id); renderFilters(); }));
  }
  const s = $("f-street"); s.replaceChildren();
  for (const o of options.streets) {
    s.append(chip(o.label, filters.streets.includes(o.id), () => { toggle(filters.streets, o.id); renderFilters(); }));
  }
}

// ---------- drill ----------

async function nextSpot() {
  if (busy) return;
  busy = true;
  try {
    current = await api("/api/equity/next", filters);
    chosen = { bucket: null, decision: null };
    renderSpot(current);
    show("drill-screen");
    shownAt = performance.now();
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function renderSpot(s) {
  $("spot-tags").replaceChildren(
    el("span", { class: "tag strong" }, s.game_label),
    el("span", { class: "tag" }, s.street === "flop" ? "Flop" : "Turn"),
    el("span", { class: "tag" }, "Villain: random hand"),
  );
  $("board").replaceChildren(...s.board.map(renderCard));
  const hero = $("hero-cards");
  hero.className = s.hero_cards.length > 2 ? "cards four" : "cards";
  hero.replaceChildren(...s.hero_cards.map(renderCard));
  $("bet-line").replaceChildren(
    "Pot ", el("b", {}, `${num(s.pot_bb)}bb`),
    " · Villain bets ", el("b", {}, `${num(s.bet_bb)}bb`),
    " · To call ", el("b", {}, `${num(s.to_call_bb)}bb`),
  );
  const grid = $("buckets"); grid.replaceChildren();
  for (const b of s.buckets) {
    grid.append(el("button", {
      class: "chip bucket", type: "button", "aria-pressed": "false", "data-id": b.id,
      onclick: () => pick("bucket", b.id),
    }, b.label));
  }
  for (const d of ["fold", "call"]) {
    $(`d-${d}`).setAttribute("aria-pressed", "false");
    $(`d-${d}`).disabled = false;
  }
}

function pick(kind, value) {
  if (busy) return;
  chosen[kind] = value;
  if (kind === "bucket") {
    for (const b of document.querySelectorAll(".bucket")) {
      b.setAttribute("aria-pressed", String(b.dataset.id === value));
    }
  } else {
    for (const d of ["fold", "call"]) $(`d-${d}`).setAttribute("aria-pressed", String(d === value));
  }
  if (chosen.bucket && chosen.decision) submit();
}

async function submit() {
  busy = true;
  const elapsed = Math.round(performance.now() - shownAt);
  for (const b of document.querySelectorAll("#drill-screen button")) b.disabled = true;
  try {
    const r = await api("/api/equity/answer", {
      game: current.game, street: current.street,
      hero_cards: current.hero_cards, board: current.board,
      pot_bb: current.pot_bb, bet_bb: current.bet_bb,
      bucket: chosen.bucket, decision: chosen.decision,
      response_time_ms: elapsed,
    });
    renderResult(current, r);
    show("result-screen");
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

// ---------- result ----------

function renderResult(s, r) {
  updateScore(r.summary);
  const gb = $("g-bucket");
  gb.className = `grade-banner small ${r.bucket.grade}`;
  gb.replaceChildren(el("span", { class: "gl" }, "Equity guess"), GRADE_WORDS[r.bucket.grade]);
  const gd = $("g-decision");
  gd.className = `grade-banner small ${r.decision.grade}`;
  gd.replaceChildren(el("span", { class: "gl" }, `You ${r.decision.chosen === "call" ? "called" : "folded"}`),
    GRADE_WORDS[r.decision.grade]);

  const margin = r.exact ? "exact" : `±${r.margin_pct}, ${r.iterations.toLocaleString()} simulated hands`;
  $("equity-big").replaceChildren(
    "Your equity ", el("b", {}, r.equity_pct), el("span", { class: "muted" }, ` (${margin})`));

  // Meter: equity fill with a marker at the equity needed to call.
  const eq = Math.min(100, r.equity * 100);
  const req = r.decision.required * 100;
  $("equity-meter").replaceChildren(
    el("div", { class: "meter" },
      el("i", { class: r.equity >= r.decision.required ? "fill good" : "fill bad", style: `width:${eq}%` }),
      el("span", { class: "need", style: `left:${req}%` })),
    el("div", { class: "meter-labels" },
      // keep the label on screen when the marker is near an edge
      el("span", { style: `left:${Math.min(Math.max(req, 12), 88)}%` }, `need ${r.decision.required_pct}`)),
  );

  $("bucket-expl").textContent =
    `You picked ${r.bucket.chosen_label}. ` + r.bucket.explanation;
  $("decision-expl").textContent = r.decision.explanation;

  renderTips($("tips"), r.tips);
  $("r-board").replaceChildren(...s.board.map(renderCard));
  $("r-hero").replaceChildren(...s.hero_cards.map(renderCard));
  $("method").textContent =
    "Equity is computed: hands simulated against one random opponent hand, scored by PokerKit." +
    (s.game === "plo" ? " Omaha rules: exactly two hole cards and three board cards." : "");
}

// ---------- startup ----------

document.addEventListener("keydown", (e) => {
  if (!$("result-screen").hidden && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    nextSpot();
  }
});

$("d-fold").addEventListener("click", () => pick("decision", "fold"));
$("d-call").addEventListener("click", () => pick("decision", "call"));
$("filters-btn").addEventListener("click", () => { renderFilters(); show("filters-screen"); });
$("start-btn").addEventListener("click", () => { saveJSON(FILTER_KEY, filters); nextSpot(); });
$("next-btn").addEventListener("click", nextSpot);

(async function init() {
  try {
    options = await api("/api/equity/options");
    updateScore(await api(`/api/summary?drill_type=${SCORE_DRILL}`));
  } catch (e) {
    showMessage("Can't reach the trainer server: " + e.message);
    return;
  }
  const saved = loadJSON(FILTER_KEY);
  if (saved) {
    filters.games = (saved.games || []).filter((g) => options.games.some((o) => o.id === g));
    filters.streets = (saved.streets || []).filter((s) => options.streets.some((o) => o.id === s));
  }
  nextSpot();
})();
