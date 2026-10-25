# Poker Trainer: Build Brief

## What this is

A drill-based poker trainer for No-Limit Texas Hold'em (NLHE) and Pot-Limit Omaha (PLO). The app shows a spot, the user makes a decision, and the app grades it immediately against a trusted answer key, then tracks weak areas and drills them more often.

The user is Adam. He plays mostly cash games, wants tournaments too, and builds by vibe coding with Claude Code. He is not a professional developer, so explain decisions in plain language, keep the setup simple, and make every phase usable on its own before starting the next one.

This is a trainer, not a poker game. Playing full hands against bots is out of scope.

## Ground rules (read these first)

1. **Never invent poker strategy, and never ship unverified advice.** Strategy and advice must never come from the AI's own memory: LLM poker strategy is unreliable and would train bad habits. Every piece of advice in the app is one of:
   - **Computed**: worked out mathematically by the program (equity, pot-limit math, push/fold equilibria, solver output), labelled with the method.
   - **Sourced and verified**: taken from named outside sources and passed the verification standard below, with the evidence stored next to it.
   - **Contested / unverified**: anything that failed or hasn't finished verification. Stored, never shown as advice. The app may list it as "sources disagree" with the evidence.
   Adam does not review advice himself; the verification standard is the gate.

   **Verification standard** (every item must pass all of it before it is shown):
   1. *The source exists and says it.* Fetch the actual page or document and store the quote or data with the link, author/publisher and the date checked. Nothing from memory.
   2. *Independent corroboration.* At least two unrelated reputable sources agree (solver-based publishers, established training sites, books with named authors). Forums and unattributed charts don't count. Disagreement means contested, not a coin flip.
   3. *Consistent with the math.* Where the program can compute the answer, the source must agree with it (push/fold ranges vs the solver, odds claims vs the formula, nut claims vs the Omaha engine, chart sanity checks). A failed check is a failed verification.
   4. *Explicit scope.* Each item records exactly which spots it applies to (game, format, positions, stack depth, spot types, streets, hand categories) and is only ever shown inside that scope.
   5. *Reviewable.* Every piece of advice on screen offers "Why trust this?", showing sources, quotes, check date and the checks it passed.
   Where credible sources differ on a detail (for example open-raise sizes) the app says so and names each, rather than picking silently.
2. **Every answer key records its source.** Chart files carry a `source` field. Computed answers are labeled `computed` with the method.
3. **Do not write a hand evaluator or rules engine.** Use PokerKit for game rules, hand evaluation, and equity. Read its current docs and verify the API before using it rather than assuming function names.
4. **Correctness is tested.** Anything that grades the user (pot-limit math, equity, chart lookup, grading thresholds) needs unit tests with known values before the UI depends on it.
5. **Sample data is clearly fake.** To build and test the chart pipeline before real charts exist, create small sample charts marked `"source": {"name": "SAMPLE - NOT REAL STRATEGY"}` and show a visible warning in the UI whenever one is in use.
6. Ask Adam before adding a dependency, changing the stack, or making a strategy-related judgment call.

## Stack

- Python 3.11+ backend with FastAPI
- PokerKit for rules, hand evaluation, and equity calculations
- SQLite for drill history and progress
- Front end: plain HTML, CSS, and vanilla JavaScript served by FastAPI, no build step. Mobile-first, since Adam will drill on his phone. Big tap targets, cards readable at phone width.
- pytest for tests

Keep it runnable locally with one command (document it in README.md). Deployment comes later.

## Architecture

Four separate layers, so new games, charts, and drills plug in without rewrites:

1. **Game layer** (`trainer/game/`): thin wrapper over PokerKit. Dealing, hand evaluation, equity, pot math. No strategy here.
2. **Scenario generator** (`trainer/scenarios/`): builds a spot from parameters: game, format (cash/tournament), table size, hero position, stack depth in big blinds, blinds/antes, action before hero, bet sizes. Random within whatever constraints the drill sets.
3. **Answer keys / graders** (`trainer/graders/`): one per drill type. Takes a spot plus the user's answer, returns the correct answer, a grade, and a short explanation built from the data (for example "CO raises A5s 60% of the time in this chart"). Graders either look up a chart or compute the answer.
4. **Drill engine and progress** (`trainer/drills/`, `trainer/progress/`): picks the next spot, records attempts, weights future spots toward weak areas.

Suggested layout:

```
trainer/
  game/
  scenarios/
  graders/
  drills/
  progress/
  api/            FastAPI routes
data/
  charts/
    nlhe/
    plo/
    pushfold/
  equity_cache/
web/              HTML, CSS, JS
tests/
```

## Chart data format

One JSON file per spot. Hand keys for NLHE use the standard 169 hand classes (`AA`, `AKs`, `AKo`, ... `32o`). Values are action frequencies that sum to 1.0. Hands missing from the file default to fold, and the loader should warn on missing hands rather than fail silently.

```json
{
  "id": "nlhe-cash-6max-100bb-rfi-CO",
  "game": "nlhe",
  "format": "cash",
  "table_size": 6,
  "stack_bb": 100,
  "spot": {
    "type": "rfi",
    "hero_pos": "CO",
    "villain_pos": null,
    "facing": null
  },
  "actions": ["fold", "raise_2.5"],
  "source": {
    "name": "",
    "url": "",
    "notes": ""
  },
  "hands": {
    "AA": {"raise_2.5": 1.0},
    "A5s": {"raise_2.5": 0.6, "fold": 0.4},
    "72o": {"fold": 1.0}
  }
}
```

Positions:
- 6-max: UTG, HJ, CO, BTN, SB, BB
- 9-handed: UTG, UTG1, UTG2, LJ, HJ, CO, BTN, SB, BB

Spot types for phase 1:
- `rfi`: everyone folded to hero; fold or raise
- `vs_open`: one player opened; fold, call, or 3-bet
- `vs_3bet`: hero opened and got 3-bet; fold, call, or 4-bet

Build an importer that converts common range-string notation into this format, since that's how most charts are published. Example input: `AA,KK,QQ,AKs,AQs:0.5,A5s:0.6`. Also accept `22+`, `A2s+`, `KTo+` style shorthand. Test the importer thoroughly; a parsing bug here silently corrupts every answer.

## Grading mixed strategies

Charts often mix actions. Grade by the frequency of the action the user chose:

- 0.5 or higher: **correct**
- 0.15 to 0.5: **acceptable (mixed)**, show the full frequencies
- under 0.15: **wrong**

Keep these thresholds in one config value so Adam can tune them.

## Phases

Build in order. Each phase ends with something Adam can actually use and a short summary of what was built and how to run it.

### Phase 1: NLHE cash preflop trainer

- Chart loader, range-string importer, sample charts (marked fake)
- Scenario generator for `rfi`, `vs_open`, `vs_3bet` at 6-max and 9-handed, 100bb
- Drill screen: shows table size, positions, stack depth, the action so far, hero's two cards; buttons for the legal actions
- Result screen: grade, chart frequencies for this hand, a compact view of the full range for this spot with hero's hand highlighted
- Filters: choose table size, positions, and spot types to drill
- Record every attempt in SQLite

### Phase 2: Equity and pot odds drill (NLHE and PLO)

- Deal hero's hand, a flop or turn, a pot size, and a bet facing hero. Villain holds a random hand to start; ranges come later.
- User does two things: estimates equity (buckets: under 20, 20-30, 30-40, 40-50, 50-60, 60+) and decides call or fold
- Grade with PokerKit equity by Monte Carlo, fixed iteration count, seedable for tests
- Required equity to call = call / (pot + bet + call). Call is correct when equity meets or beats that.
- Label this clearly as direct odds only. Implied odds are ignored in this drill and the UI should say so.
- Supports both NLHE (2 cards) and PLO (4 cards, must use exactly two hole cards and three board cards, which PokerKit handles)

### Phase 3: PLO drills

**Nut awareness.** Show a board (flop, turn, or river) and hero's four cards. Questions, each graded by computation:
- What is the current nut hand? (multiple choice)
- Does hero have the nuts?
- On flop/turn: is hero drawing to the nuts, a non-nut hand, or neither?

**Pot-limit sizing.** Show the pot and the action in the current betting round; user enters the maximum raise.

Max raise formula, where `pot` includes every chip already in the middle plus all bets made this round:

```
amount_to_call = largest_bet_this_round - hero_chips_already_in_this_round
max_raise_to   = largest_bet_this_round + pot + amount_to_call
```

Required tests:
- Blinds 1/2, UTG first to act preflop: pot = 3, facing 2, to call 2 → max raise to 7
- Pot 100 postflop, villain bets 100, hero has nothing in: pot = 200, to call 100 → max raise to 400

### Phase 4: Tournament push/fold

- Short-stack spots, 15 big blinds and under, with antes as a parameter
- Compute equilibrium push/fold ranges with the program itself (chip EV, no ICM yet). Start heads-up (SB vs BB), where the solution is straightforward with iterative best response over the 169 hand classes. Extend to more players afterward.
- Precompute the 169 x 169 preflop all-in equity table once and cache it in `data/equity_cache/`; it takes a while.
- Save results in the same chart format with `"source": {"name": "computed", "notes": "<method, iterations, chip EV>"}` so the phase 1 trainer UI reuses them.
- ICM and deeper-stacked tournament play are out of scope for now.

### Phase 5: Leak tracking

- Each attempt stores: timestamp, drill type, game, all spot parameters, hero hand, user answer, correct answer, grade, response time.
- Stats screen: accuracy by drill type, position, spot type, and hand category (pairs, suited aces, offsuit broadways, and so on).
- Drill engine weights sampling toward categories with low accuracy, with simple spaced repetition so missed spots come back sooner.
- "Drill my leaks" mode that only serves weak categories.

## Out of scope for now

- Playing full hands against bots
- Hand history import from poker sites
- Postflop solver integration for NLHE strategy
- ICM
- User accounts and deployment

These are likely future phases, so keep the layers clean enough that they could be added.

## Open questions for Adam

Ask these when they become relevant, not all up front:

- Which chart sources to use for NLHE cash (and PLO preflop, if any). Until then, sample charts only.
- Open-raise sizes he wants to drill (6-max online usually differs from live 9-handed games)
- Rake assumptions, if his chart source distinguishes them
- Whether to add 40bb or 200bb stack depths after 100bb works
