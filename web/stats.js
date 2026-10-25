// Stats screen: accuracy by drill, position, spot type and hand category. Shared helpers in common.js.
"use strict";

const WEAK = 0.7;
const MIN_N = 5;

function pct(x) {
  return x == null ? "–" : `${Math.round(x * 100)}%`;
}

function statRow(label, r) {
  const weak = r.total >= MIN_N && r.score < WEAK;
  return el("div", { class: `stat-row${weak ? " weak" : ""}`, title: `${r.correct} correct, ${r.acceptable} acceptable, ${r.wrong} wrong` },
    el("span", { class: "k" }, label),
    el("div", { class: "stack-bar" },
      el("i", { class: "c", style: `width:${r.correct / r.total * 100}%` }),
      el("i", { class: "a", style: `width:${r.acceptable / r.total * 100}%` }),
      el("i", { class: "w", style: `width:${r.wrong / r.total * 100}%` })),
    el("span", { class: "n" }, `${pct(r.accuracy)} · ${r.total}`));
}

function section(title, rows, labelOf, note) {
  const sec = el("section", { class: "stat-section" }, el("h2", {}, title));
  if (!rows || !rows.length) {
    sec.append(el("p", { class: "empty" }, "No hands yet."));
    return sec;
  }
  const list = el("div", { class: "stat-rows" });
  for (const r of rows) list.append(statRow(labelOf ? labelOf(r) : String(r.key), r));
  sec.append(list);
  if (note) sec.append(el("p", { class: "hint" }, note));
  return sec;
}

function leakBox(p) {
  const l = p.leaks;
  const parts = [];
  if (l.weak_positions.length) parts.push(["Weak positions: ", l.weak_positions.join(", ")]);
  if (l.weak_spot_types.length) parts.push(["Weak spot types: ", l.weak_spot_types.join(", ")]);
  if (l.weak_categories.length) parts.push(["Weak hand categories: ", l.weak_categories.join(", ")]);
  const box = el("div", { class: "leak-box" });
  if (!parts.length) {
    box.append(`No leaks found yet. A category counts as a leak once you've played it at least ${MIN_N} times and score under ${WEAK * 100}% (an "acceptable" answer counts half).`);
  } else {
    for (const [a, b] of parts) box.append(el("div", {}, a, el("b", {}, b)));
    box.append(el("div", { class: "hint" }, `Turn on "Drill my leaks" in the Preflop filters to practise only these.`));
  }
  box.append(el("div", {}, "Spots due for review: ", el("b", {}, String(p.reviews.due)),
    el("span", { class: "muted" }, ` (${p.reviews.total} being tracked)`)));
  return box;
}

function trend(grades) {
  const sec = el("section", { class: "stat-section" }, el("h2", {}, "Last 30 preflop hands (oldest → newest)"));
  if (!grades.length) { sec.append(el("p", { class: "empty" }, "No hands yet.")); return sec; }
  const t = el("div", { class: "trend" });
  for (const g of [...grades].reverse()) t.append(el("i", { class: g, title: g }));
  sec.append(t);
  return sec;
}

async function load() {
  const main = $("stats");
  try {
    const s = await api("/api/stats");
    main.replaceChildren();
    $("score").textContent = `${s.total_attempts} answers`;
    if (!s.total_attempts) {
      main.append(el("p", { class: "empty" }, "Nothing recorded yet. Play some hands on any tab and come back."));
      return;
    }
    main.append(section("By drill", s.drills, (r) => r.label));
    main.append(el("section", { class: "stat-section" }, el("h2", {}, "Preflop leaks"), leakBox(s.preflop)));
    main.append(section("Preflop by position", s.preflop.by_position));
    main.append(section("Preflop by spot type", s.preflop.by_spot_type, (r) => r.label));
    main.append(section("Preflop by hand category", s.preflop.by_category));
    main.append(section("Preflop by format", s.preflop.by_format));
    main.append(trend(s.preflop.recent));
    main.append(section("Equity: call/fold by street", s.equity.by_street));
    main.append(section("Equity: call/fold by game", s.equity.by_game, (r) => ({ nlhe: "Hold'em", plo: "Omaha" })[r.key] || r.key));
    main.append(section("Nuts: naming the nuts, by street", s.nuts.by_street));
    main.append(section("Pot limit by stage", s.pot_limit.by_stage));
    main.append(el("p", { class: "source" }, "Bars: green correct, yellow acceptable, red wrong. Red labels are leaks (under 70% with at least 5 answers)."));
  } catch (e) {
    main.replaceChildren(el("p", { class: "error" }, "Couldn't load stats: " + e.message));
  }
}

$("refresh-btn").addEventListener("click", load);
load();
