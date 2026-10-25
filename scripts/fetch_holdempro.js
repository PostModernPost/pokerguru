// Render HoldemPro's free preflop page in Chromium and read every chart's cell titles.
// Usage: node scripts/fetch_holdempro.js out.json
const { chromium } = require('playwright');
(async () => {
  const out = process.argv[2] || 'holdempro.json';
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 2000 } });
  await p.goto('https://holdempro.app/tools/preflop-ranges', { waitUntil: 'networkidle', timeout: 90000 });
  // Close any pop-up that sits over the page (sign-up / cookie dialogs).
  await p.keyboard.press('Escape');
  await p.waitForTimeout(300);
  const result = {};
  // Every clickable control whose text is a seat or "BB vs X"
  const controls = await p.$$('button, [role=tab], a');
  const labels = [];
  for (const c of controls) {
    const t = ((await c.textContent()) || '').trim();
    if (/^(UTG|MP|CO|BTN|SB|BB vs (UTG|MP|CO|BTN|SB))$/.test(t)) labels.push(t);
  }
  const uniq = [...new Set(labels)];
  for (const label of uniq) {
    const ctl = (await p.$$(`button:text-is("${label}"), [role=tab]:text-is("${label}"), a:text-is("${label}")`))[0];
    if (!ctl) continue;
    await ctl.evaluate((e) => e.click());   // JS click: not blocked by overlays
    await p.waitForTimeout(500);
    const cells = await p.$$eval('button[title]', els => els.map(e => e.getAttribute('title')).filter(t => /^[AKQJT2-9]{2}[so]? — /.test(t)));
    const heading = await p.$$eval('h1, h2, h3', els => els.map(e => e.textContent.trim()).filter(Boolean).slice(0, 6));
    result[label] = { cells, heading };
  }
  require('fs').writeFileSync(out, JSON.stringify(result, null, 1));
  console.log(Object.entries(result).map(([k, v]) => `${k}: ${v.cells.length} cells; ${v.cells[0]} | ${v.cells[168]}`).join('\n'));
  await b.close();
})();
