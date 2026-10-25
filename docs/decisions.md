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

## Phase 3 (PLO nuts and pot-limit sizing)

| Decision | Choice | How to change / why |
|---|---|---|
| What "the nuts" means | The best hand anyone can hold **given your cards** (blockers count). Tying it counts as having it. | This matches how players talk ("I have the nut flush" with the ace). When your cards block a stronger hand the board allows, the result says so. The abstract version is one line in `trainer/game/omaha.py` (`nut_info`). |
| What counts as "drawing" | The next card only (no two-card "backdoor" draws), and only to a straight or better that beats your current hand | Keeps the question answerable at the table. `STRONG_LABELS` in `omaha.py` sets the categories. |
| Multiple-choice distractors | The strongest other hands possible on the board, plus your own hand if it isn't the nuts | `quiz_options` in `trainer/graders/plo.py`. Four options total. |
| Grading | Exact right/wrong (no "acceptable"), since these are facts, not estimates | `trainer/graders/plo.py` |
| Pot-limit answers | Must match exactly; whole chips only | Spots are generated so the answer is always a whole number. |
| Pot-limit blinds and sizes | Blinds 1/2, 2/5, 5/10 in chips; 6-max preflop with random folds, calls, pot raises and smaller raises before you; postflop pots 5-100bb with a bet of 33-100% of the pot, sometimes a caller, sometimes nobody has bet | `POT_LIMIT_*` in `trainer/config.py`. Chips, not big blinds, because that's how pot-limit math is done at the table. |
| Tampering guard | The pot-limit answer is never sent to the phone with the question; the server rebuilds the spot from the action history when grading | `trainer/api/plo_routes.py` |
| Score shown on the Nuts tab | Accuracy on question 1 (naming the nuts); all three questions are stored separately | Phase 5 will show them all. |

## Phase 4 (tournament push/fold)

| Decision | Choice | How to change / why |
|---|---|---|
| Players | **Heads-up only** (SB shoves or folds, BB calls or folds). | The brief says start heads-up and extend afterward. Extending properly needs multi-way all-in equities and callers behind callers; the common shortcuts give wrong ranges, and wrong charts train bad habits. Left for a later phase, honestly labelled. |
| Stacks and antes | 3-15bb in 1bb steps; ante 0 and 0.125bb per player (close to a 12.5% ante). | `PUSHFOLD_STACKS_BB`, `PUSHFOLD_ANTES_BB` in `trainer/config.py`, then `python scripts/build_pushfold_charts.py`. |
| Equity table | 169x169, seeded Monte Carlo, 40,000 boards per matchup (about +/-0.25%), PokerKit ranks every showdown. Committed. | Exact enumeration would take days in Python; this takes 10 minutes. `scripts/build_equity_table.py --samples N` rebuilds it. |
| numpy | Added as a dependency. | The brief says ask first; you asked me to decide. Without it the table would take many hours. |
| Solver | Fictitious play, 600 iterations, chip EV, card removal between the two hands. Exploitability (how much a perfect opponent could gain) is written into each chart's notes; it is a few thousandths of a big blind per hand. | `PUSHFOLD_ITERATIONS` in config. |
| Mixed hands | Frequencies between 0 and 1 are kept as-is, so the usual mixed-strategy grading applies (an "acceptable" answer near the edge). | These hands are genuinely close to indifferent. |
| Where they appear | As real (non-sample) charts in the Preflop drill under Format: Tournament, table size Heads-up, spot types "Push or fold" and "Facing a shove". | Chart files in `data/charts/pushfold/`. |

## Phase 5 (leak tracking)

| Decision | Choice | How to change / why |
|---|---|---|
| What counts as a leak | Score under 70% with at least 5 answers; an "acceptable" answer counts half a point. | `WEAK_SCORE`, `MIN_ATTEMPTS` in `trainer/drills/preflop.py` (shown on the Stats page). |
| Hand categories | pair, suited ace, offsuit ace, suited broadway, offsuit broadway, suited connector (one apart), suited other, offsuit other. | `hand_category` in `trainer/game/hand_classes.py`. |
| Weighting | Chart weight = 1 + 4 x (how far below 100% you score in its position and spot type); the same for hand categories half the time. Unknown areas count as mildly weak so they get explored. | `WEIGHT_GAIN`, `CATEGORY_CHANCE` in `trainer/drills/preflop.py`. |
| Spaced repetition | Counted in hands, not days (you drill in bursts). A miss returns after 5 hands, an "acceptable" after 12; each correct answer doubles the gap (minimum 25); past 200 the spot graduates. Due reviews are served about a third of the time. | `REVIEW_*` in `trainer/progress/store.py`, `REVIEW_CHANCE` in the drill. |
| Scope of weighting | Preflop drill only; the other drills are random but all of them report to Stats. | Their spots have no chart/hand to key on; weighting by street or game is a small follow-up. |
| Database | Schema version 2 adds a `reviews` table; an old database upgrades itself. | `trainer/progress/store.py` |

## Phase 6 (advice library and verification)

| Decision | Choice | How to change / why |
|---|---|---|
| Rule change | Ground rule 1 now allows sourced advice that passes a written verification standard; Adam asked not to review tips himself, so the standard is the gate. | `CLAUDE.md` |
| What "verified" requires | Pages fetched and the exact quote found; two unrelated publishers; any applicable math check passes; explicit scope; evidence viewable in the app. | Enforced by the loader (`trainer/advice/library.py`) and set by `scripts/verify_tips.py`. |
| Failure handling | A quote not found on its page or a failed math check marks the tip **contested**; a page that can't be fetched leaves it **unverified**. Neither is ever shown as advice. | `scripts/verify_tips.py` |
| Math checks | Six cross-checks against the program's own calculations (pot odds, rule of 2 and 4, pot-limit formula, shorter stacks shove wider, antes widen ranges, suited beats offsuit). | `trainer/advice/math_checks.py` |
| Up to 3 tips per result | Narrowest scope first. | `AdviceLibrary.matching(limit=3)` |
| First batch | Nine tips drafted with candidate sources from web searches on 2026-10-25, all `unverified` because the build environment's network policy blocked fetching the source pages. The math checks all pass. | Run `verify_tips.py` once network access allows it. |

## Phase 1 decisions

See `docs/phase1-summary.md`.
