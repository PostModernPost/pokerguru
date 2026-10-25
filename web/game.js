// Game mode: a continuous simulated cash game. The server runs the hand (PokerKit) and the bots;
// this page shows the table, takes your action, and shows the attention card and feedback.
"use strict";

const GAME_KEY = "pokerguru.game";
let options = null;
let settings = { players: 9, small_blind: 1, big_blind: 2, buy_in_bb: 100, bots: "standard", feedback: true, attention: true };
let session = null;   // session id
let state = null;
let busy = false;

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) { /* keep status text */ }
    throw new Error(msg);
  }
  return r.json();
}

function money(x) { return "$" + num(x); }

// Range-grid colours (same scheme as the Preflop drill).
const KIND_COLORS = { allin: "var(--allin)", raise: "var(--raise)", call: "var(--call)", fold: "var(--fold)" };
const KIND_ORDER = ["allin", "raise", "call", "fold"];
function actionKind(id) { return id === "fold" || id === "call" || id === "allin" ? id : (id.startsWith("raise") ? "raise" : "fold"); }
function gradientFor(freqs, actions) {
  const parts = actions.map((a, i) => ({ kind: actionKind(a.id), f: freqs[i] })).filter((p) => p.f > 0)
    .sort((x, y) => KIND_ORDER.indexOf(x.kind) - KIND_ORDER.indexOf(y.kind));
  if (parts.length === 1) return KIND_COLORS[parts[0].kind];
  let at = 0; const stops = [];
  for (const p of parts) { const end = at + p.f * 100; stops.push(`${KIND_COLORS[p.kind]} ${at}% ${end}%`); at = end; }
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

async function showChart(chartId, handClass) {
  let c;
  try { c = await api("/api/chart/" + encodeURIComponent(chartId)); } catch (e) { alert(e.message); return; }
  $("chart-title").textContent = `${c.hero_pos}${c.villain_pos ? " vs " + c.villain_pos : ""} · ${c.spot_label} · ${c.table_size}-handed`;
  const legend = $("chart-legend"); legend.replaceChildren();
  for (const a of c.actions) legend.append(el("span", { style: `--c:${KIND_COLORS[actionKind(a.id)]}` }, a.label));
  const grid = $("chart-grid"); grid.replaceChildren();
  for (const row of c.grid) for (const hand of row) {
    const w = c.deal_weights ? c.deal_weights[hand] : 1;
    grid.append(el("div", {
      class: `cell${hand === handClass ? " hero" : ""}${w === 0 ? " out" : ""}`,
      title: hand + ": " + (w === 0 ? "not opened from here" : c.actions.map((a, i) => `${a.label} ${Math.round(c.range[hand][i] * 100)}%`).join(", ")),
      style: `background:${gradientFor(c.range[hand], c.actions)}`,
    }, hand));
  }
  $("chart-source").textContent = "Chart source: " + (c.source.name || "unknown") + (c.source.status === "contested" ? " † sources disagree" : c.source.status === "single_source" ? " * one publisher" : "");
  $("chart-dialog").showModal();
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(GAME_KEY) || "null");
    if (saved) { settings = { ...settings, ...(saved.settings || {}) }; session = saved.session || null; }
  } catch (_) { /* defaults */ }
}
function save() {
  try { localStorage.setItem(GAME_KEY, JSON.stringify({ settings, session })); } catch (_) { /* ignore */ }
}

// ---------- setup ----------
function renderSetup() {
  const p = $("s-players"); p.replaceChildren();
  for (const n of options.players) p.append(chip(`${n}`, settings.players === n, () => { settings.players = n; renderSetup(); }));
  $("s-sb").value = settings.small_blind; $("s-bb").value = settings.big_blind; $("s-buyin").value = settings.buy_in_bb;
  const b = $("s-bots"); b.replaceChildren();
  for (const o of options.bots) b.append(chip(o.label, settings.bots === o.id, () => { settings.bots = o.id; renderSetup(); }));
  const h = $("s-help"); h.replaceChildren(
    chip("Pay attention card", settings.attention, () => { settings.attention = !settings.attention; renderSetup(); }),
    chip("Feedback after each decision", settings.feedback, () => { settings.feedback = !settings.feedback; renderSetup(); }),
  );
  $("setup-error").hidden = true;
}

async function startGame() {
  settings.small_blind = Number($("s-sb").value) || 1;
  settings.big_blind = Number($("s-bb").value) || 2;
  settings.buy_in_bb = Number($("s-buyin").value) || 100;
  try {
    state = await api("/api/game/new", { ...settings, step: true });
  } catch (e) {
    $("setup-error").textContent = e.message; $("setup-error").hidden = false; return;
  }
  session = state.id; save();
  render(); showScreen("game-screen");
  busy = true;
  try { await playBots(); } finally { busy = false; }
}

function showScreen(id) {
  for (const s of ["setup-screen", "game-screen", "message-screen"]) $(s).hidden = s !== id;
  window.scrollTo(0, 0);
}

// ---------- table ----------
function renderCards(container, cards) {
  container.replaceChildren();
  for (const c of cards || []) container.append(renderCard(c));
}

function render() {
  const h = state.hand, hero = state.seats.find((s) => s.is_hero);
  renderGameTable($("game-table"), state);
  $("bots-note").textContent = "‡ " + state.bots_note;
  renderCards($("hero-cards"), hero.cards);
  $("score").textContent = (hero.net >= 0 ? "+" : "−") + money(Math.abs(hero.net));
  $("hand-line").textContent = `Hand ${state.hand_no} · ${h.street} · pot ${money(h.pot)}`;
  $("hero-line").textContent = `You are ${hero.pos} with ${money(hero.stack)}${hero.buy_ins > 1 ? ` (buy-in ${hero.buy_ins})` : ""}`;

  // attention card
  const att = h.attention || [];
  $("attention").hidden = !(h.hero_turn && att.length);
  const al = $("attention-list"); al.replaceChildren();
  for (const a of att) {
    const title = a.gloss && window.openGlossaryTerm
      ? el("button", { type: "button", class: "att-title term-btn", title: "Tap for what this means", onclick: () => window.openGlossaryTerm(a.gloss) }, a.title + " ⓘ")
      : el("div", { class: "att-title" }, a.title);
    const value = a.value_gloss && window.openGlossaryTerm
      ? el("button", { type: "button", class: "att-value term-btn big", title: "Tap for what this seat is", onclick: () => window.openGlossaryTerm(a.value_gloss) }, a.value)
      : el("div", { class: "att-value" }, a.value ?? a.text ?? "");
    al.append(el("div", { class: "att-tile" }, title, value, el("div", { class: "att-detail" }, a.detail || "")));
  }

  // actions
  const legal = h.legal || {};
  $("actions").hidden = !h.hero_turn;
  $("hand-line").textContent += h.waiting_on_bots ? " · opponents acting…" : "";
  if (h.hero_turn) {
    $("btn-fold").hidden = !legal.can_fold;
    $("btn-call").textContent = legal.to_call ? `Call ${money(legal.to_call)}` : "Check";
    const canRaise = legal.min_raise_to != null;
    $("raise-box").hidden = !canRaise;
    if (canRaise) {
      const sizes = [];
      const pot = h.pot, toCall = legal.to_call;
      const after = pot + toCall; // pot after calling
      const add = (label, to) => { to = Math.round(Math.max(legal.min_raise_to, Math.min(legal.max_raise_to, to))); if (!sizes.some((s) => s.to === to)) sizes.push({ label, to }); };
      const bb = state.config.big_blind;
      if (h.street === "preflop") add("3bb", 3 * bb);  // the standard live open; shown first before the flop
      if (toCall === 0) { add("⅓ pot", pot / 3); add("½ pot", pot / 2); add("⅔ pot", pot * 2 / 3); add("Pot", pot); }
      else { add("Min", legal.min_raise_to); add("2.5×", legal.min_raise_to * 1.25 + toCall); add("Pot", legal.pot_raise_to); }
      if (h.street !== "preflop") add("3bb", 3 * bb);
      add("All-in", legal.max_raise_to);
      const sc = $("size-chips"); sc.replaceChildren();
      for (const s of sizes) sc.append(chip(`${s.label} ${money(s.to)}`, false, () => { $("raise-amount").value = s.to; }));
      $("raise-amount").min = legal.min_raise_to; $("raise-amount").max = legal.max_raise_to;
      $("raise-amount").value = sizes[0].to;
      $("btn-raise").textContent = toCall ? "Raise to" : "Bet";
      const ac = $("add-chips"); ac.replaceChildren();
      const bump = (d) => {
        const cur = Number($("raise-amount").value) || legal.min_raise_to;
        $("raise-amount").value = Math.max(legal.min_raise_to, Math.min(legal.max_raise_to, cur + d));
        updateRaiseHint(legal);
      };
      for (const d of [1, 5, 25, 100]) ac.append(chip(`+$${d}`, false, () => bump(d)));
      ac.append(chip("Reset", false, () => { $("raise-amount").value = legal.min_raise_to; updateRaiseHint(legal); }));
      updateRaiseHint(legal);
    }
  }

  // feedback for the last decision
  renderFeedback($("feedback"), state.feedback);
  const notes = $("hand-notes"); notes.hidden = false;
  const nl = $("hand-notes-list"); nl.replaceChildren();
  if (!state.hand_feedback.length) nl.append(el("p", { class: "muted" }, "Nothing graded yet this hand."));
  state.hand_feedback.map((f, i) => ({ f, n: i + 1 })).reverse().forEach(({ f, n }) => {
    const d = el("div", { class: "note" }); renderFeedback(d, f, n); nl.append(d);
  });

  // result
  $("result").hidden = !h.finished;
  $("next-btn").hidden = !h.finished;
  if (h.finished && state.result) {
    const r = state.result, box = $("result"); box.replaceChildren();
    const net = r.hero_net;
    const banner = net > 0 ? `You won ${money(net)}` : net < 0 ? (r.hero_folded ? `You folded; down ${money(-net)} (your blind)` : `You lost ${money(-net)}`)
      : (r.hero_folded ? "You folded before putting money in" : "You broke even");
    box.append(el("div", { class: `grade-banner ${net > 0 ? "correct" : net < 0 ? "wrong" : "neutral"}` }, banner));
    for (const w of r.winners) {
      const who = w.is_hero ? "You" : w.name;
      box.append(el("p", { class: "winner-line" }, el("b", {}, `${who} win${w.is_hero ? "" : "s"} ${money(w.amount)}`),
        r.by_fold ? " (everyone else folded)." : ` with ${w.hand}.`));
    }
    if (r.board.length) box.append(el("p", { class: "muted" }, "Board: " + r.board.join(" ")));
    for (const srow of r.shown) {
      const row = el("div", { class: `shown-row${srow.won > 0 ? " won" : ""}` },
        el("span", { class: "shown-name" }, (srow.is_hero ? "You" : srow.name) + ":"));
      const cc = el("div", { class: "cards small" }); renderCards(cc, srow.cards); row.append(cc);
      row.append(el("span", { class: "shown-hand" }, srow.hand + (srow.won > 0 ? ` · wins ${money(srow.won)}` : "")));
      box.append(row);
    }
  }

  // log
  const ll = $("log-list"); ll.replaceChildren();
  const numbered = h.events.map((e, i) => ({ ...e, n: i + 1 })).reverse();
  for (const e of numbered) {
    const who = e.pos ? `${e.name} (${e.pos})` : "";
    const text = e.kind === "win" ? `${e.name === "You" ? "You win" : e.name + " wins"} ${money(e.amount)} (${e.text})` :
      e.kind === "deal" ? `${e.street}: ${e.text}` :
      e.kind.startsWith("post") ? `${who} posts ${money(e.amount)}` :
      e.kind === "call" ? `${who} calls ${money(e.amount)}` :
      e.kind === "check" ? `${who} checks` : e.kind === "fold" ? `${who} folds` :
      e.kind === "allin" ? `${who} is all-in for ${money(e.amount)}` :
      `${who} ${e.kind === "bet" ? "bets" : "raises to"} ${money(e.amount)}`;
    ll.append(el("li", { class: e.kind === "win" ? "log-win" : "" }, el("span", { class: "log-n" }, `${e.n}.`), " ", text));
  }
}

function updateRaiseHint(legal) {
  const v = Number($("raise-amount").value);
  $("raise-hint").textContent = `Between ${money(legal.min_raise_to)} and ${money(legal.max_raise_to)} total${v > legal.max_raise_to || v < legal.min_raise_to ? " · will be adjusted to the nearest legal amount" : ""}`;
}

function renderFeedback(box, f, n) {
  box.replaceChildren();
  if (!f) { box.hidden = true; return; }
  box.hidden = false;
  const grade = f.grade ? el("span", { class: `grade-pill ${f.grade}` }, { correct: "Correct", acceptable: "Acceptable (mixed)", wrong: "Wrong" }[f.grade]) : el("span", { class: "grade-pill none" }, "No grade");
  box.append(el("div", { class: "fb-head" }, el("b", {}, (n ? `${n}. ` : "") + f.title), grade));
  if (f.action) box.append(el("p", { class: "fb-action" }, `You ${f.action}` + (f.street ? ` on the ${f.street}` : "") + "."));
  for (const line of f.lines) box.append(el("p", {}, line));
  if (f.chart) {
    const fr = el("div", { class: "freqs" });
    for (const x of f.chart.frequencies) {
      fr.append(el("div", { class: "freq-row" }, el("span", { class: "label" }, x.label),
        el("div", { class: "bar" }, el("i", { style: `width:${x.freq * 100}%` })), el("span", { class: "pct" }, Math.round(x.freq * 100) + "%")));
    }
    box.append(fr);
    const src = el("p", { class: "source" }, "Chart: " + f.chart.source + " ");
    if (f.chart.chart_id) src.append(el("button", { type: "button", class: "link-btn", onclick: () => showChart(f.chart.chart_id, f.chart.hand_class) }, "Show the full chart"));
    box.append(src);
  }
  for (const n of f.footnotes) box.append(el("p", { class: "footnote" }, n));
}

// ---------- actions ----------
const STEP_MS = { fold: 260, check: 300, default: 420 };

// Bots act one at a time, with a short pause between moves, so the table can be followed.
async function playBots() {
  while (state?.hand?.waiting_on_bots) {
    const before = state.hand.events.length;
    state = await api("/api/game/step", { session });
    render();
    const last = state.hand.events[state.hand.events.length - 1];
    const moved = state.hand.events.length > before;
    await new Promise((r) => setTimeout(r, moved ? (STEP_MS[last?.kind] || STEP_MS.default) : 50));
  }
}

async function act(action, amount) {
  if (busy || !state?.hand?.hero_turn) return;
  busy = true;
  try {
    state = await api("/api/game/act", { session, action, amount, step: true });
    render();
    await playBots();
  } catch (e) {
    if (/No such game/.test(e.message)) { session = null; save(); showScreen("setup-screen"); renderSetup(); }
    else alert(e.message);
  } finally { busy = false; }
}

async function nextHand() {
  if (busy) return;
  busy = true;
  try { state = await api("/api/game/next", { session, step: true }); render(); await playBots(); } catch (e) { alert(e.message); } finally { busy = false; }
}

$("btn-fold").addEventListener("click", () => act("fold"));
$("btn-call").addEventListener("click", () => act(state.hand.legal.to_call ? "call" : "check"));
$("btn-raise").addEventListener("click", () => act("raise", Number($("raise-amount").value)));
$("next-btn").addEventListener("click", nextHand);
$("chart-close").addEventListener("click", () => $("chart-dialog").close());
$("new-game-btn").addEventListener("click", () => {
  if (!confirm("Start a new game? This table, its stacks and the running result are discarded. Your graded decisions stay in Stats.")) return;
  session = null; state = null; save(); renderSetup(); showScreen("setup-screen");
});
$("raise-amount").addEventListener("input", () => state?.hand?.legal && updateRaiseHint(state.hand.legal));
$("start-btn").addEventListener("click", startGame);
$("setup-btn").addEventListener("click", () => { renderSetup(); showScreen("setup-screen"); });

(async () => {
  load();
  try { options = await api("/api/game/options"); } catch (e) { $("message").textContent = "Can't reach the trainer server: " + e.message; showScreen("message-screen"); return; }
  if (session) {
    try { state = await api("/api/game/state", { session }); render(); showScreen("game-screen"); return; }
    catch (_) { session = null; save(); }
  }
  renderSetup(); showScreen("setup-screen");
})();
