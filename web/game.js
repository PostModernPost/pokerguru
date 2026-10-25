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
    state = await api("/api/game/new", settings);
  } catch (e) {
    $("setup-error").textContent = e.message; $("setup-error").hidden = false; return;
  }
  session = state.id; save();
  render(); showScreen("game-screen");
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
  for (const a of att) al.append(el("div", { class: "att-tile" },
    el("div", { class: "att-title" }, a.title), el("div", { class: "att-value" }, a.value ?? a.text ?? ""), el("div", { class: "att-detail" }, a.detail || "")));

  // actions
  const legal = h.legal || {};
  $("actions").hidden = !h.hero_turn;
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
      if (toCall === 0) { add("⅓ pot", pot / 3); add("½ pot", pot / 2); add("⅔ pot", pot * 2 / 3); add("Pot", pot); }
      else { add("Min", legal.min_raise_to); add("2.5×", legal.min_raise_to * 1.25 + toCall); add("Pot", legal.pot_raise_to); }
      add("All-in", legal.max_raise_to);
      const sc = $("size-chips"); sc.replaceChildren();
      for (const s of sizes) sc.append(chip(`${s.label} ${money(s.to)}`, false, () => { $("raise-amount").value = s.to; }));
      $("raise-amount").min = legal.min_raise_to; $("raise-amount").max = legal.max_raise_to;
      $("raise-amount").value = sizes[0].to;
      $("btn-raise").textContent = toCall ? "Raise to" : "Bet";
    }
  }

  // feedback for the last decision
  renderFeedback($("feedback"), state.feedback);
  const notes = $("hand-notes"); notes.hidden = state.hand_feedback.length < 2;
  const nl = $("hand-notes-list"); nl.replaceChildren();
  for (const f of state.hand_feedback) { const d = el("div", { class: "note" }); renderFeedback(d, f); nl.append(d); }

  // result
  $("result").hidden = !h.finished;
  $("next-btn").hidden = !h.finished;
  if (h.finished && state.result) {
    const r = state.result, box = $("result"); box.replaceChildren();
    const net = r.hero_net;
    box.append(el("div", { class: `grade-banner ${net > 0 ? "correct" : net < 0 ? "wrong" : "acceptable"}` },
      net > 0 ? `You won ${money(net)}` : net < 0 ? `You lost ${money(-net)}` : "No change"));
    box.append(el("p", {}, `Winner: ${r.winners.join(", ")}.` + (r.board.length ? ` Board ${r.board.join(" ")}.` : "")));
    for (const [name, cards] of Object.entries(r.shown)) {
      const row = el("div", { class: "shown-row" }, el("span", {}, name + ": "));
      const cc = el("div", { class: "cards small" }); renderCards(cc, cards); row.append(cc); box.append(row);
    }
  }

  // log
  const ll = $("log-list"); ll.replaceChildren();
  for (const e of h.events) {
    const who = e.pos ? `${e.name} (${e.pos})` : "";
    const text = e.kind === "deal" ? `${e.street}: ${e.text}` :
      e.kind.startsWith("post") ? `${who} posts ${money(e.amount)}` :
      e.kind === "call" ? `${who} calls ${money(e.amount)}` :
      e.kind === "check" ? `${who} checks` : e.kind === "fold" ? `${who} folds` :
      e.kind === "allin" ? `${who} is all-in for ${money(e.amount)}` :
      `${who} ${e.kind === "bet" ? "bets" : "raises to"} ${money(e.amount)}`;
    ll.append(el("li", {}, text));
  }
  $("log").open = false;
}

function renderFeedback(box, f) {
  box.replaceChildren();
  if (!f) { box.hidden = true; return; }
  box.hidden = false;
  const grade = f.grade ? el("span", { class: `grade-pill ${f.grade}` }, { correct: "Correct", acceptable: "Acceptable (mixed)", wrong: "Wrong" }[f.grade]) : el("span", { class: "grade-pill none" }, "No grade");
  box.append(el("div", { class: "fb-head" }, el("b", {}, f.title), grade));
  for (const line of f.lines) box.append(el("p", {}, line));
  if (f.chart) {
    const fr = el("div", { class: "freqs" });
    for (const x of f.chart.frequencies) {
      fr.append(el("div", { class: "freq-row" }, el("span", { class: "label" }, x.label),
        el("div", { class: "bar" }, el("i", { style: `width:${x.freq * 100}%` })), el("span", { class: "pct" }, Math.round(x.freq * 100) + "%")));
    }
    box.append(fr);
    box.append(el("p", { class: "source" }, "Chart: " + f.chart.source));
  }
  for (const n of f.footnotes) box.append(el("p", { class: "footnote" }, n));
}

// ---------- actions ----------
async function act(action, amount) {
  if (busy || !state?.hand?.hero_turn) return;
  busy = true;
  try {
    state = await api("/api/game/act", { session, action, amount });
    render();
  } catch (e) {
    if (/No such game/.test(e.message)) { session = null; save(); showScreen("setup-screen"); renderSetup(); }
    else alert(e.message);
  } finally { busy = false; }
}

async function nextHand() {
  if (busy) return;
  busy = true;
  try { state = await api("/api/game/next", { session }); render(); } catch (e) { alert(e.message); } finally { busy = false; }
}

$("btn-fold").addEventListener("click", () => act("fold"));
$("btn-call").addEventListener("click", () => act(state.hand.legal.to_call ? "call" : "check"));
$("btn-raise").addEventListener("click", () => act("raise", Number($("raise-amount").value)));
$("next-btn").addEventListener("click", nextHand);
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
