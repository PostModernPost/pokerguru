// Helpers shared by every drill page. Plain JavaScript, no build step.
"use strict";

const $ = (id) => document.getElementById(id);
const SUITS = { s: "♠", h: "♥", d: "♦", c: "♣" };

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

function show(screen) {
  for (const s of ["filters-screen", "drill-screen", "result-screen", "message-screen"]) {
    if (!$(s)) continue;
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

function chip(label, pressed, onClick) {
  return el("button", { class: "chip", "aria-pressed": String(pressed), type: "button", onclick: onClick }, label);
}

function toggle(list, value) {
  const i = list.indexOf(value);
  if (i >= 0) list.splice(i, 1); else list.push(value);
}

function saveJSON(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* storage unavailable */ }
}

function loadJSON(key) {
  try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (_) { return null; }
}
