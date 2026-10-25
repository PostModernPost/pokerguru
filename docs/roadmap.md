# Roadmap

Ordered for Adam's actual situation: a monthly live cash game, 9 players, $200 buy-in at $1/$2 (100bb), mostly
Hold'em with multi-board hands, bomb pots (Hold'em and Omaha) and Pineapple later in the night,
a mix of strong and loose players. He has played a lot but never studied. Phases 1-10 are done, and the computed core of phase 11
(see `docs/decisions.md`). Most useful next thing first.

The one recurring constraint: **the program never invents strategy** (CLAUDE.md ground rule 1).
"Computed" means the program works it out from the rules and the math; "needs a source" means
real published strategy has to be found and verified first; "AI opinion" is allowed only in the
game mode and is always marked.

| # | Phase | What it adds | Why it comes here | Strategy source |
|---|---|---|---|---|
| 10 | **Live full-ring preflop charts** (done) | Real charts for 9-handed tables: open-raise, facing an open from every seat, facing a 3-bet. Sample charts go off by default until each spot has a real chart. | Preflop at a full table is the decision Adam makes most often in his game, and today those spots are either missing or fake (the AQs screenshot). | **Needs a source**; same fetch-and-corroborate process as phase 7. |
| 11 | **Game mode** (core done; AI coach next) | A continuous simulated game: Hold'em or Omaha, cash or tournament, 2-9 players, buy-in in big blinds. Feedback on every decision: charts preflop, pot odds and equity on calls, hand-strength facts, all computed or sourced; everything else from an AI model, marked as AI opinion. Bots play the charts preflop and a simple strength-and-odds policy after. Every graded decision feeds the leak tracker. | Adam expects to use this most. It only becomes trustworthy after phase 10 gives it real full-ring charts. | Charts and math where they exist; **AI opinion** (Claude API, Adam's own key, works without it but with no AI feedback) elsewhere. |
| 12 | **Hand reading: ranges, not hands** | In the Equity drill the opponent holds a *range* taken from the charts in the app ("a button opener"), with loose and tight presets so Adam can practise against the kind of players actually at his table. | His table mixes strong and loose players; equity against a random hand is a warm-up for that. | Ranges come from loaded charts; the presets are widened or narrowed versions of them, labelled as such. |
| 13 | **Home-game variants** | Computed drills for what his game plays after the first few hours: double-board nuts and "who scoops, who splits"; bomb-pot spots (everyone sees a multiway flop, Hold'em and Omaha) for hand strength, nut awareness and pot odds; Pineapple "which card do you discard?" graded by equity. | These are the hours where the pots get big and nobody at the table has studied. Published strategy is thin, so only computed drills. | Computed. Exact house rules from Adam. |
| 14 | **Sessions, streaks and leak weighting everywhere** | Short fixed-length sessions ("twenty hands before the game"), a streak, a pre-game warm-up that serves the weak areas from every drill, and the phase-5 weighting extended to Equity, Nuts, Pot limit and the game mode. | A monthly game rewards steady drilling between games more than cramming. | None needed. |
| 15 | **Deeper stacks** | 150bb and 200bb cash charts and spots, since live games run deeper than 100bb once people rebuy. | His game is 100bb at the start but rebuys make it deeper. | Needs a source. |
| 16 | **Deployment and sync** | Fly.io with a passcode and a persistent disk so it works on his phone away from home, progress shared between phone and desktop. | Convenience; moves up whenever Adam wants it. | None needed. |
| 17 | **Postflop decision drills (Hold'em)** | Continuation bets, check-raises, sizing, graded against solver output; would also replace AI opinion in the game mode with verified answers. | The biggest learning gain and the biggest job; needs solver output as the source. | Needs a solver or solver-output files. |
| 18 | **Tournaments: multi-player push/fold, 20-25bb spots, ICM** | Full-table shove-or-fold, the stage where it's no longer just push or fold, and prize-money adjustments. | Only when Adam starts playing tournaments. | Computed. |
| 19 | **Hand history import** | Load real online hands and find where play deviated from the charts. | Only useful if he plays online. | Charts already in the app. |

## Plan for remote access (not built yet)

Adam wants the app on his phone away from home eventually; for now it runs on the desktop and
over home Wi-Fi. Vercel is fine for the app itself but keeps no files between runs, so the
progress database must live in a database service: Supabase (Postgres), which Adam already has.

Design rules kept now so this stays a short job later:
1. All state lives in the progress store (`trainer/progress/store.py`); nothing else is written
   at runtime. Precomputed tables and charts are repo files, read-only.
2. Every answer is recomputed on the server from the spot, so requests are independent.

Work when the time comes (about half a day):
- A Postgres implementation of `AttemptStore` behind the same methods (SQLite stays the local default).
- A `PASSCODE` setting checked on every request, since the app would be public.
- A Vercel configuration for the FastAPI app; background equity/nuts work becomes on-request
  (a second or two) since serverless functions don't keep threads alive.
- Alternative if Vercel's limits bite (numpy size, cold starts): Fly.io or Render with a small
  persistent disk, which needs no database change at all.

## Done since the brief

- **Phase 6, advice library**, **Phase 7, real 6-max preflop charts**, **Phase 8, basics drill**
  (hand naming, outs, price) plus a double-click Windows launcher, and **Phase 9, "Why this hand?"**:
  see `docs/decisions.md`. **Phase 10** added 80 real 9-handed charts (every seat, every spot
  type). Still on sample data, and therefore off by default: 6-max facing a 3-bet and 6-max
  seats other than the big blind facing an open.

- **Glossary** (added after phase 5): every jargon word in the app is underlined with dots; tapping
  it opens a pop-up with a plain-language definition over the current screen, and closing it (or
  the phone's back button) returns you exactly where you were. "All terms" lists everything by
  group. Source: `web/glossary.json`; a readable copy is in `docs/glossary.md`.
