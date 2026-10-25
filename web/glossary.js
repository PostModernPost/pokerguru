// Glossary: underlines jargon anywhere on the page and explains it in a pop-up
// that leaves the screen behind it exactly as it was. Shared by every page.
"use strict";

(function () {
  const SKIP = "button, a, input, select, textarea, dialog, svg, .table-wrap, .card, .cards, .range-grid, .seats, .num-display, .keypad, .trend, .stack-bar, .grade-banner, [data-no-gloss]";
  let entries = [];          // [{key, term, definition, group, names: [...]}]
  let byName = new Map();    // lowercase name -> entry
  let exactRe = null;        // case-sensitive, for all-caps abbreviations (UTG, EV, ...)
  let looseRe = null;        // case-insensitive, everything else
  let dialog, titleEl, bodyEl, listBtn;
  let pushedState = false;
  let showingList = false;
  let savedScroll = 0;   // where the page was when the pop-up opened; put back on close
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const isAbbrev = (s) => /^[A-Z0-9]{2,5}$/.test(s);

  function build(data) {
    for (const g of data.groups) {
      for (const t of g.terms) {
        const names = [t.term, ...(t.aliases || [])];
        const e = { key: t.term.toLowerCase(), term: t.term, definition: t.definition, group: g.title, names };
        entries.push(e);
        for (const n of names) byName.set(n.toLowerCase(), e);
      }
    }
    const all = [...byName.keys()].sort((a, b) => b.length - a.length);
    const exact = [], loose = [];
    for (const e of entries) for (const n of e.names) (isAbbrev(n) ? exact : loose).push(n);
    const pat = (list) => `(?<![A-Za-z0-9'])(?:${list.sort((a, b) => b.length - a.length).map(escapeRe).join("|")})(?![A-Za-z0-9])`;
    exactRe = exact.length ? new RegExp(pat(exact), "g") : null;
    looseRe = loose.length ? new RegExp(pat(loose), "gi") : null;
    void all;
  }

  // ---------- linking ----------

  function textNodes(root) {
    const out = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        const parent = node.parentElement;
        if (!parent || parent.closest(SKIP) || parent.closest(".term")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    let n;
    while ((n = walker.nextNode())) out.push(n);
    return out;
  }

  function matchesIn(text) {
    const found = [];
    for (const re of [exactRe, looseRe]) {
      if (!re) continue;
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text))) {
        const entry = byName.get(m[0].toLowerCase());
        if (entry) found.push({ start: m.index, end: m.index + m[0].length, entry });
      }
    }
    found.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
    const out = [];
    let last = 0;
    for (const f of found) {
      if (f.start >= last) { out.push(f); last = f.end; }
    }
    return out;
  }

  function linkAll(root) {
    if (!entries.length) return;
    // Each term is underlined once per screen, so text doesn't turn into a sea of links.
    const done = new Set([...root.querySelectorAll(".term")].map((b) => b.dataset.term));
    for (const node of textNodes(root)) {
      const text = node.nodeValue;
      const found = matchesIn(text).filter((f) => !done.has(f.entry.key));
      if (!found.length) continue;
      const frag = document.createDocumentFragment();
      let pos = 0;
      for (const f of found) {
        if (done.has(f.entry.key)) continue;
        done.add(f.entry.key);
        frag.append(text.slice(pos, f.start));
        const b = document.createElement("button");
        b.type = "button";
        b.className = "term";
        b.dataset.term = f.entry.key;
        b.title = "Tap for the meaning";
        b.textContent = text.slice(f.start, f.end);
        b.addEventListener("click", (ev) => { ev.stopPropagation(); openTerm(f.entry); });
        frag.append(b);
        pos = f.end;
      }
      frag.append(text.slice(pos));
      node.parentNode.replaceChild(frag, node);
    }
  }

  // ---------- pop-up ----------

  function buildDialog() {
    dialog = document.createElement("dialog");
    dialog.id = "glossary-dialog";
    dialog.innerHTML = `
      <div class="gd-head">
        <h2 id="gd-title">Glossary</h2>
        <button type="button" class="icon-btn" id="gd-close" aria-label="Close">Close</button>
      </div>
      <div class="gd-body" id="gd-body"></div>
      <div class="gd-foot"><button type="button" class="big-btn" id="gd-list">All terms</button></div>`;
    document.body.append(dialog);
    titleEl = dialog.querySelector("#gd-title");
    bodyEl = dialog.querySelector("#gd-body");
    listBtn = dialog.querySelector("#gd-list");
    dialog.querySelector("#gd-close").addEventListener("click", closeDialog);
    listBtn.addEventListener("click", () => (showingList ? closeDialog() : showList()));
    // Keep the drills' keyboard shortcuts (Enter = next hand, 1-9 = actions) from firing underneath.
    dialog.addEventListener("keydown", (e) => e.stopPropagation());
    dialog.addEventListener("click", (e) => { if (e.target === dialog) closeDialog(); });
    dialog.addEventListener("close", () => {
      if (pushedState) { pushedState = false; history.back(); }
      restoreScroll();
    });
    try { history.scrollRestoration = "manual"; } catch (_) { /* older browsers */ }
    window.addEventListener("popstate", () => {
      // The phone's back button closes the pop-up instead of leaving the page.
      if (dialog.open) { pushedState = false; dialog.close(); }
      restoreScroll();
    });
  }

  function restoreScroll() {
    const y = savedScroll;
    requestAnimationFrame(() => window.scrollTo(0, y));
    setTimeout(() => window.scrollTo(0, y), 50);
  }

  function open() {
    if (dialog.open) return;
    savedScroll = window.scrollY;
    try { history.pushState({ glossary: true }, ""); pushedState = true; } catch (_) { pushedState = false; }
    dialog.showModal();
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
  }

  function openTerm(entry) {
    showingList = false;
    titleEl.textContent = cap(entry.term);
    const also = entry.names.slice(1);
    bodyEl.replaceChildren(
      el("p", { class: "gd-def" }, entry.definition),
      el("p", { class: "gd-meta" }, (also.length ? `Also written: ${also.join(", ")} · ` : "") + entry.group),
    );
    listBtn.textContent = "All terms";
    open();
    bodyEl.scrollTop = 0;
  }

  function showList() {
    showingList = true;
    titleEl.textContent = "Glossary";
    const groups = new Map();
    for (const e of entries) {
      if (!groups.has(e.group)) groups.set(e.group, []);
      groups.get(e.group).push(e);
    }
    const frag = document.createDocumentFragment();
    frag.append(el("p", { class: "gd-meta" }, "Definitions only, no strategy. Dotted words anywhere in the app open these."));
    for (const [title, list] of groups) {
      frag.append(el("h3", {}, title));
      for (const e of list.sort((a, b) => a.term.localeCompare(b.term))) {
        frag.append(el("div", { class: "gd-item" }, el("b", {}, e.term), " ", e.definition));
      }
    }
    bodyEl.replaceChildren(frag);
    listBtn.textContent = "Close";
    open();
    bodyEl.scrollTop = 0;
  }

  // ---------- startup ----------

  async function init() {
    try {
      const res = await fetch("/glossary.json");
      build(await res.json());
    } catch (_) {
      return; // no glossary, no links; the app still works
    }
    buildDialog();
    const openBtn = document.getElementById("glossary-open");
    if (openBtn) openBtn.addEventListener("click", showList);

    const roots = [document.querySelector("main"), ...document.querySelectorAll("#sample-warning")].filter(Boolean);
    for (const r of roots) linkAll(r);
    let timer = null;
    const observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => { for (const r of roots) linkAll(r); }, 60);
    });
    for (const r of roots) observer.observe(r, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
