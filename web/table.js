// Draws the table for a preflop spot: seats in real seating order (clockwise), you at the
// bottom, the dealer button, blinds and bets as chips, folded seats greyed out, and the
// preflop action order numbered. Pure SVG, no library. Used by the Preflop drill.
"use strict";

(function () {
  const NS = "http://www.w3.org/2000/svg";
  const W = 640, H = 396;          // drawing units; the SVG scales to its container
  const CX = W / 2, CY = 182;      // felt centre; leaves room for seats above and below
  const RX = 220, RY = 112;        // the felt
  const SEAT_RX = 268, SEAT_RY = 150;  // where seat badges sit
  const CHIP_RX = 170, CHIP_RY = 78;   // where chips (blinds/bets) sit, inside the felt

  function svgEl(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function num(x) { return String(+Number(x).toFixed(2)); }

  // Angle for seat i of n with the hero at the bottom; seats go clockwise around the table.
  function angleFor(i, n, heroIndex) {
    const steps = (i - heroIndex + n) % n;
    return Math.PI / 2 + (2 * Math.PI * steps) / n;   // PI/2 = bottom (SVG y grows downward)
  }

  // spot.seats: [{pos, status: hero|fold|raise|waiting, to_bb, blind}], in preflop action order,
  // which is also clockwise seating order (UTG ... BTN, SB, BB).
  window.renderTable = function (container, spot) {
    if (!container) return;
    const seats = spot.seats || [];
    const n = seats.length;
    const heroIndex = Math.max(0, seats.findIndex((s) => s.status === "hero"));
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "table-svg", role: "img",
      "aria-label": `${n}-handed table, you are ${spot.hero_pos}` });

    // Felt and rail
    svg.append(svgEl("ellipse", { cx: CX, cy: CY, rx: RX + 14, ry: RY + 14, class: "rail" }));
    svg.append(svgEl("ellipse", { cx: CX, cy: CY, rx: RX, ry: RY, class: "felt" }));
    if (spot.pot_bb != null) {
      svg.append(svgEl("text", { x: CX, y: CY - 4, class: "pot-label", "text-anchor": "middle" }, "Pot"));
      svg.append(svgEl("text", { x: CX, y: CY + 20, class: "pot-value", "text-anchor": "middle" }, `${num(spot.pot_bb)}bb`));
    }

    // Who acts in what order preflop, among players who haven't folded yet.
    let order = 0;
    seats.forEach((seat, i) => {
      const a = angleFor(i, n, heroIndex);
      const x = CX + SEAT_RX * Math.cos(a), y = CY + SEAT_RY * Math.sin(a);
      const g = svgEl("g", { class: `seat-g ${seat.status}`, transform: `translate(${x} ${y})` });
      g.append(svgEl("rect", { x: -34, y: -22, width: 68, height: 44, rx: 10, class: "seat-box" }));
      g.append(svgEl("text", { x: 0, y: -3, class: "seat-pos", "text-anchor": "middle" }, seat.pos));
      const sub = seat.status === "hero" ? "You" : seat.status === "fold" ? "folded" :
        seat.status === "raise" ? "raised" : seat.blind != null ? "blind" : "to act";
      g.append(svgEl("text", { x: 0, y: 14, class: "seat-sub", "text-anchor": "middle" }, sub));
      // Preflop action order badge (1 = first to act).
      order += 1;
      g.append(svgEl("circle", { cx: 30, cy: -20, r: 9, class: "order-badge" }));
      g.append(svgEl("text", { x: 30, y: -16.5, class: "order-text", "text-anchor": "middle" }, String(order)));
      svg.append(g);

      // Chips in front of the seat: posted blind, or the raise amount.
      const amount = seat.status === "raise" ? seat.to_bb : (seat.status !== "fold" ? seat.blind : null);
      if (amount != null && seat.status !== "fold") {
        const cx = CX + CHIP_RX * Math.cos(a), cy = CY + CHIP_RY * Math.sin(a);
        const cls = seat.status === "raise" ? "chip raise" : "chip blind";
        svg.append(svgEl("circle", { cx, cy, r: 11, class: cls }));
        svg.append(svgEl("text", { x: cx, y: cy + 24, class: "chip-text", "text-anchor": "middle" }, `${num(amount)}bb`));
      }
      // Dealer button beside the BTN seat (heads-up: the SB is the button).
      const isButton = seat.pos === "BTN" || (n === 2 && seat.pos === "SB");
      if (isButton) {
        const bx = CX + (SEAT_RX - 52) * Math.cos(a + 0.28), by = CY + (SEAT_RY - 30) * Math.sin(a + 0.28);
        svg.append(svgEl("circle", { cx: bx, cy: by, r: 10, class: "dealer" }));
        svg.append(svgEl("text", { x: bx, y: by + 4, class: "dealer-text", "text-anchor": "middle" }, "D"));
      }
    });

    // Direction of play hint.
    svg.append(svgEl("text", { x: CX, y: H - 4, class: "table-hint", "text-anchor": "middle" },
      "Action goes clockwise · numbers show who acts first preflop"));
    container.replaceChildren(svg);
  };
})();
