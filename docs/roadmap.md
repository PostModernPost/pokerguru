# Roadmap: possible future phases

Ordered by how much each would help a relatively new player, most useful first. Phases 1-5
from the original brief are done. None of these is started; this is a menu, not a plan.

The one recurring constraint: **the program never invents strategy** (CLAUDE.md ground rule 1).
Anything marked "needs a source" means Adam has to pick where the strategy comes from; anything
marked "computed" the program can work out from the rules and the math.

| # | Phase | What it adds | Why it matters for a newer player | Strategy source |
|---|---|---|---|---|
| 6 | **Real cash-game charts** | Replace the fake sample charts with real preflop ranges for 6-max and 9-handed, 100bb. The importer and the drill are ready; only the data is missing. | Preflop is the decision you make most often, and the only drill that currently can't teach you anything. Everything else in the app is already real. | **Needs a source** (a chart pack or book you trust). |
| 7 | **Hand-strength and pot-odds basics drill** | Quick-fire questions: "what's your hand?" on a board (Hold'em and Omaha), "how many outs?", "what are the pot odds here?" with the math shown. | Reading your own hand fast and correctly is the first skill, and the equity drill assumes you already can. Counting outs is the bridge between "I have a draw" and "should I call". | Computed. |
| 8 | **Why-this-hand explanations** | On the result screen, show what the hand has going for it in plain words: pair, suited, connected, blockers, how it ranks against the rest of the range in this spot (top 10%, middle, bottom). Plus a one-tap glossary for every term (done: see below). | Charts tell you *what*; a beginner needs a sense of *why* so it transfers to spots the chart doesn't cover. This describes the hand, it doesn't invent advice. | Computed from the chart and the cards. |
| 9 | **Multi-player push/fold** | 3-handed and full-table shove-or-fold charts, including facing a shove with players still to act behind you. | Short-stack tournament play is where new players bleed chips fastest, and heads-up charts only cover the very end of a tournament. | Computed (a real piece of work: multi-way equities and callers behind callers). |
| 10 | **Hand reading: ranges, not hands** | In the equity drill, the villain holds a *range* (e.g. "the hands a button opener has") instead of a random hand. Start with ranges taken from the charts already in the app. | "Equity against a random hand" is a warm-up. Real decisions are against what an opponent would actually play. | Ranges come from the loaded charts, so no new strategy is invented. |
| 11 | **Session mode and goals** | Timed or fixed-length sessions, a daily streak, "ten hands before work", a session summary screen. | Habit beats intensity. New players improve by drilling a little every day. | None needed. |
| 12 | **Leak weighting for every drill** | Extend the phase-5 weighting (weak areas come up more often, misses return sooner) from the Preflop drill to the Equity, Nuts and Pot-limit drills. | Same learning engine everywhere; small job. | None needed. |
| 13 | **Deeper and shallower stacks** | 40bb and 200bb cash charts, and 20-25bb tournament spots (where it's no longer just push or fold). | Live games are often deeper than 100bb; tournaments spend a long time at 20-40bb. | Needs a source for charts; some tournament spots can be computed. |
| 14 | **ICM for tournaments** | Value tournament chips in prize money, so push/fold ranges tighten near the money and at final tables. | Matters a lot in the last 10% of a tournament; not much before. Lower priority until the basics are solid. | Computed (needs payout structures as input). |
| 15 | **Postflop decision drills (Hold'em)** | Continuation bets, check-raises, bet sizing postflop, graded against solver output. | Postflop is where the money is, but trustworthy answers need a solver's output as the source, which is a large dependency. | Needs a solver or solver-output files. |
| 16 | **Hand history import** | Load real hands you played (from an online site) and find the spots where you deviated from the charts. | Turns the trainer into a review tool for your own play. | Charts already in the app. |
| 17 | **Deployment and sync** | Run it on a small server so it works away from home Wi-Fi, with progress synced across phone and computer. | Convenience, not learning. | None needed (hosting choice from Adam). |
| 18 | **Play full hands against bots** | Explicitly out of scope in the brief. Listed only so it isn't forgotten. | Fun, but a trainer teaches more per minute than a game. | Needs real bot strategy. |

## Done since the brief

- **Glossary** (added after phase 5): every jargon word in the app is underlined with dots; tapping
  it opens a pop-up with a plain-language definition over the current screen, and closing it (or
  the phone's back button) returns you exactly where you were. "All terms" lists everything by
  group. Source: `web/glossary.json`; a readable copy is in `docs/glossary.md`.
