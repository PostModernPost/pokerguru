// Advice block on result screens: verified tips with a "Why trust this?" evidence pop-up.
// Shared by every drill page. Uses the glossary dialog's styling via its own <dialog>.
"use strict";

(function () {
  let dialog = null;
  let pushed = false;

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.id = "advice-dialog";
    dialog.innerHTML = `
      <div class="gd-head"><h2>Why trust this?</h2>
        <button type="button" class="icon-btn" id="ad-close" aria-label="Close">Close</button></div>
      <div class="gd-body" id="ad-body"></div>`;
    document.body.append(dialog);
    dialog.querySelector("#ad-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("keydown", (e) => e.stopPropagation());
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => { if (pushed) { pushed = false; history.back(); } });
    window.addEventListener("popstate", () => { if (dialog.open) { pushed = false; dialog.close(); } });
    return dialog;
  }

  async function showEvidence(tipId) {
    const d = ensureDialog();
    const body = d.querySelector("#ad-body");
    body.replaceChildren(el("p", { class: "gd-meta" }, "Loading…"));
    const y = window.scrollY;
    try { history.pushState({ advice: true }, ""); pushed = true; } catch (_) { pushed = false; }
    if (!d.open) d.showModal();
    try {
      const t = await api(`/api/advice/${encodeURIComponent(tipId)}`);
      const ev = t.evidence;
      const frag = document.createDocumentFragment();
      frag.append(el("p", { class: "gd-def" }, t.text));
      frag.append(el("p", { class: "gd-meta" }, `Status: ${ev.status}. Shown only because it passed every check below.`));
      frag.append(el("h3", {}, "Sources"));
      for (const s of ev.sources) {
        frag.append(el("div", { class: "gd-item" },
          el("b", {}, s.publisher), ` — ${s.name} `,
          el("a", { href: s.url, target: "_blank", rel: "noopener" }, "link"),
          el("br"), el("em", {}, `“${s.quote}”`), el("br"),
          el("span", { class: "muted" }, `Checked ${s.accessed}`)));
      }
      frag.append(el("h3", {}, "Checks"));
      for (const c of ev.checks) {
        frag.append(el("div", { class: "gd-item" }, el("b", {}, (c.passed ? "✓ " : "✗ ") + c.type.replace("_", " ")), ` ${c.detail}`));
      }
      if (ev.notes) frag.append(el("p", { class: "gd-meta" }, ev.notes));
      body.replaceChildren(frag);
    } catch (e) {
      body.replaceChildren(el("p", { class: "error" }, "Couldn't load the evidence: " + e.message));
    }
    d.addEventListener("close", () => requestAnimationFrame(() => window.scrollTo(0, y)), { once: true });
  }

  // Render tips into a container. Called by each drill's renderResult.
  window.renderTips = function (container, tips) {
    if (!container) return;
    container.replaceChildren();
    if (!tips || !tips.length) { container.hidden = true; return; }
    container.hidden = false;
    container.append(el("h3", {}, "Advice for this spot"));
    for (const t of tips) {
      container.append(el("div", { class: "tip" },
        el("p", { class: "tip-text" }, t.text),
        el("div", { class: "tip-meta" },
          el("span", { class: "muted" }, `Sources: ${t.source_names.join(", ")}`),
          el("button", { type: "button", class: "link-btn", onclick: () => showEvidence(t.id) }, "Why trust this?"))));
    }
  };
})();
