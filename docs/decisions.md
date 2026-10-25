# Decisions log

Adam asked Claude to make the open decisions so the project can keep moving, and to adjust
them later. Each entry says what was decided, why, and how to change it.

One limit stays in place: **Claude won't choose poker strategy** (which hands to play, chart
contents). That's ground rule 1 in CLAUDE.md, because AI-written strategy is unreliable and
would train bad habits. Strategy has to come either from a source Adam supplies or from math
the program computes itself.

## Open questions from the brief (answered after phase 1)

| Question | Decision | Why / how to change |
|---|---|---|
| Which chart source for NLHE cash preflop? | **None yet. The SAMPLE charts stay**, with the red warning. | Picking or typing up a chart is choosing strategy. Phase 4 will *compute* real push/fold charts, so you'll get genuine charts without a source. When you find cash charts you trust, paste their ranges into `scripts/import_range.py`. |
| Which open-raise sizes to drill? | **Whatever the chart says.** | Sizes come from each chart file (`raise_2.5`, `facing`), so a real chart brings its own. Nothing to set. |
| Rake assumptions? | **Ignored.** | It only matters if a chart source has different charts per rake level. Revisit then. |
| Add 40bb / 200bb stacks? | **Not now; 100bb only.** | The chart format already supports any stack depth, so adding one later just means adding chart files. |

## Phase 2 (equity and pot odds drill)

| Decision | Choice | How to change |
|---|---|---|
| Simulated hands per spot | 2,500 (about ±1% accuracy) | `EQUITY_ITERATIONS` in `trainer/config.py`. Higher is more accurate but slower, PLO especially. |
| "Close enough" margin | Within 2 percentage points of the call/fold line or an equity range's edge, either answer counts as acceptable | `EQUITY_TOLERANCE` in `trainer/config.py`. The brief has no rule for simulation error; this avoids marking you wrong for a coin flip. |
| Pot sizes | 5 to 100bb (13 values) | `EQUITY_POT_SIZES_BB` |
| Bet sizes | NLHE 25% to 200% of pot; PLO 25% to 100% (pot-limit can't bet more than the pot). Rounded to 0.5bb. | `EQUITY_BET_FRACTIONS` |
| Hero's chips this round | Always zero (villain bets, hero hasn't acted yet), so the call equals the bet | Built into the drill. The grader already supports a different call amount for later drills. |
| Equity method | Own sampling loop; PokerKit evaluates every hand | PokerKit's `calculate_equities` isn't reproducible across runs with a seed. A test cross-checks the two. |
| Same spot, same answer | The random seed is derived from the cards | Grading is identical even after a server restart. |
| Score shown on the Equity tab | Call/fold accuracy | Both parts (estimate and decision) are saved as separate attempts, for phase 5. |
| Streets | Flop and turn only, as the brief says | River would be easy to add (the equity code handles it). |
| Hands dealt | Fully random, for hero and villain | Ranges come later, per the brief. |

## Phase 1 decisions

See `docs/phase1-summary.md`.
