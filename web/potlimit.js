// Pot-limit sizing drill. Shared helpers are in common.js.
"use strict";

const FILTER_KEY = "pokerguru.potLimitFilters";
const SCORE_DRILL = "plo_pot_limit";

let options = null;
let filters = { stages: [] };
let current = null;
let entry = "";
let shownAt = 0;
let busy = false;

function renderFilters() {
  const s = $("f-stage"); s.replaceChildren();
  for (const o of options.stages) {
    s.append(chip(o.label, filters.stages.includes(o.id), () => { toggle(filters.stages, o.id); renderFilters(); }));
  }
}

async function nextSpot() {
  if (busy) return;
  busy = true;
  try {
    current = await api("/api/plo/potlimit/next", filters);
    entry = "";
    renderSpot(current);
    show("drill-screen");
    shownAt = performance.now();
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function historyText(h) {
  const who = h.pos;
  switch (h.action) {
    case "fold": return `${who} folds`;
    case "check": return `${who} checks`;
    case "call": return `${who} calls ${num(h.to)}`;
    case "bet": return `${who} bets ${num(h.to)}`;
    case "raise": return `${who} raises to ${num(h.to)}`;
    default: return `${who} ${h.action}`;
  }
}

function renderSpot(s) {
  $("spot-tags").replaceChildren(
    el("span", { class: "tag strong" }, s.stage === "preflop" ? "Preflop" : "Postflop"),
    el("span", { class: "tag" }, `Blinds ${num(s.small_blind)}/${num(s.big_blind)}`),
    el("span", { class: "tag" }, `You: ${s.hero_pos}`),
  );
  const pot = $("pl-pot"); pot.replaceChildren();
  if (s.stage === "postflop") {
    pot.append("Pot at the start of this street: ", el("b", {}, num(s.pot_before_round)));
  } else {
    pot.append("Blinds posted: ", el("b", {}, `${num(s.small_blind)} + ${num(s.big_blind)}`));
    if (s.hero_in > 0) pot.append(` (you have ${num(s.hero_in)} in as the ${s.hero_pos})`);
  }
  const hist = $("pl-history"); hist.replaceChildren();
  if (!s.history.length) {
    hist.append(el("li", {}, s.stage === "preflop" ? "Everyone before you: nobody has acted yet. You're first." : "Nobody has bet yet. You're first to act."));
  } else {
    for (const h of s.history) hist.append(el("li", { class: h.action }, historyText(h)));
    hist.append(el("li", { class: "you" }, "Your turn."));
  }
  renderEntry();
  const pad = $("keypad"); pad.replaceChildren();
  for (const k of ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "."]) {
    pad.append(el("button", { class: "key", type: "button", onclick: () => key(k) }, k));
  }
}

function key(k) {
  if (busy) return;
  if (k === "⌫") entry = entry.slice(0, -1);
  else if (k === ".") { if (!entry.includes(".")) entry = (entry || "0") + "."; }
  else if (entry.length < 7) entry = entry === "0" ? k : entry + k;
  renderEntry();
}

function renderEntry() {
  $("num-display").textContent = entry || "0";
  $("submit-btn").disabled = !(entry && Number(entry) > 0);
}

async function submit() {
  if (busy || !(Number(entry) > 0)) return;
  busy = true;
  const elapsed = Math.round(performance.now() - shownAt);
  $("submit-btn").disabled = true;
  try {
    const r = await api("/api/plo/potlimit/answer", { spot: current, answer: Number(entry), response_time_ms: elapsed });
    renderResult(r);
    show("result-screen");
  } catch (e) {
    showMessage(e.message);
  } finally {
    busy = false;
  }
}

function renderResult(r) {
  updateScore(r.summary);
  const b = $("grade-banner");
  b.className = `grade-banner ${r.grade}`;
  b.textContent = r.grade === "correct" ? "Correct" : "Wrong";
  $("pl-answer").replaceChildren(
    "Your answer: ", el("b", {}, num(r.answer)), " · Correct: ", el("b", {}, num(r.correct)));
  $("explanation").textContent = r.explanation;
}

document.addEventListener("keydown", (e) => {
  if (!$("result-screen").hidden && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); nextSpot(); return; }
  if ($("drill-screen").hidden) return;
  if (/^[0-9.]$/.test(e.key)) key(e.key);
  else if (e.key === "Backspace") key("⌫");
  else if (e.key === "Enter") submit();
});

$("submit-btn").addEventListener("click", submit);
$("filters-btn").addEventListener("click", () => { renderFilters(); show("filters-screen"); });
$("start-btn").addEventListener("click", () => { saveJSON(FILTER_KEY, filters); nextSpot(); });
$("next-btn").addEventListener("click", nextSpot);

(async function init() {
  try {
    options = await api("/api/plo/potlimit/options");
    updateScore(await api(`/api/summary?drill_type=${SCORE_DRILL}`));
  } catch (e) {
    showMessage("Can't reach the trainer server: " + e.message);
    return;
  }
  const saved = loadJSON(FILTER_KEY);
  if (saved) filters.stages = (saved.stages || []).filter((s) => options.stages.some((o) => o.id === s));
  nextSpot();
})();
