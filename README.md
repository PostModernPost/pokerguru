# Poker Trainer

A drill-based trainer for No-Limit Hold'em and Pot-Limit Omaha. It shows you a spot, you
answer, and it grades you right away, either against a chart file or against math the
program computes itself.

**Current status: Phases 1 to 5 are done.** There are four drills plus a Stats page, switched
with the tabs at the top of the screen:

- **Basics:** "What's my hand?" (Hold'em and Omaha), "How many outs?" and "What's the price?",
  with the math shown. The place to start if the other drills feel fast.
- **Preflop:** NLHE. Cash spots (6-max and 9-handed, 100bb) graded against chart files, and
  tournament push/fold spots (heads-up, 3-15bb) graded against charts the program computed itself.
- **Equity:** NLHE and PLO, flop or turn. Estimate your equity, then call or fold. Graded by
  computed equity and pot odds.
- **Nuts:** PLO. What's the best possible hand on this board, do you have it, and are you drawing
  to it? Graded by checking every possible opponent holding.
- **Pot limit:** given the blinds and the action so far, what's the most you can raise to?
- **Stats:** accuracy by drill, position, spot type and hand category, your leaks, and what's due
  for review.

Only the cash preflop spots need outside charts. Everything else is computed, so those answers are
real, not samples.

For the 6-max cash preflop spots (raise first in from every seat, and the big blind facing an
open), the app now has **real charts** imported from Pokalab's published solver output and
cross-checked against a second publisher (see "Real preflop charts" below). The remaining cash spots
(9-handed, facing a 3-bet, other seats facing an open) still use
**SAMPLE charts with random made-up frequencies**. They exist to test the app. They are
**not real strategy** and the app shows a red warning whenever one is in use. Add your own
charts (see "Adding real charts" below) before you drill for real.

## Built with

| Piece | Version | What it does |
|---|---|---|
| Python | 3.11 or newer | the language |
| [PokerKit](https://github.com/uoftcprg/pokerkit) | **0.7.7** | cards, dealing, hand evaluation, equity |
| numpy | 2.5 | fast bulk hand ranking for the equity table and solver |
| FastAPI + uvicorn | 0.162 / 0.54 | the web server |
| SQLite | built into Python | stores every drill attempt |
| pytest | 9.1 | tests |

PokerKit API checked against version 0.7.7 (source and docs) before use:
- Cards: `Card.parse("AsKd")`, `Deck.STANDARD` (52 cards), each card has `.rank` and `.suit`.
- Hand evaluation: `StandardHighHand.from_game(hole, board)` for Hold'em,
  `OmahaHoldemHand.from_game(hole, board)` for Omaha (exactly 2 hole + 3 board cards).
  Hands compare with `>` / `==`.
- Equity: `calculate_equities(hole_ranges, board_cards, hole_dealing_count,
  board_dealing_count, deck, hand_types, *, sample_count=..., executor=None)`.
  Passing `[[]]` as a range means "one random hand".

The equity drill uses PokerKit's hand evaluation inside its own small sampling loop
(`trainer/game/equity.py`). PokerKit's `calculate_equities` gives different results from one
run of Python to the next even with the same seed, because it uses Python's shared random
generator and set ordering. The brief requires seedable answers, so the loop is ours, and a
test checks it against `calculate_equities`.

## The easy way to run it (Windows)

Double-click **`start.bat`** in the project folder. Every time, it:

1. **checks GitHub for a newer version** and updates itself if there is one (your progress file is
   never touched),
2. sets up Python packages the first time (about a minute),
3. starts the server and opens the app in your browser. The window it opens shows the address for
   your phone; close that window to stop.

You still need Python installed once (step 1 below).

If you double-click `start.bat` while a Poker Trainer window is already running, the new window
just opens the existing app in your browser and tells you which window to close to stop it. If
another program is using port 8000, the app moves to the next free port and prints the address.

**Updates and private repositories.** If the repository is public, updates need no login. If it's
private, GitHub will refuse the download until you give the launcher a token, once:
GitHub → your profile picture → Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token. Give it access to **only this repository**, with
Repository permissions **Contents: Read-only**, and copy the token into a new file called
`update_token.txt` next to `start.bat` (just the token, nothing else). That file is ignored by git
and never leaves your PC. If updating ever fails, the launcher says so in one line and starts the
version you have. Alternatively, install GitHub Desktop and clone the repository with it; the
launcher then updates with git instead.

## Running it on Windows (step by step)

You only do steps 1-4 once. After that, just steps 5-6 each time.

1. **Install Python 3.11 or newer** from <https://www.python.org/downloads/>.
   On the first installer screen, tick **"Add python.exe to PATH"**.
2. **Open a terminal in the project folder.** In File Explorer, open the `pokerguru`
   folder, click the address bar, type `powershell`, press Enter.
3. **Create a virtual environment** (a private box of libraries just for this project):
   ```
   python -m venv .venv
   ```
4. **Activate it and install the libraries:**
   ```
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   If PowerShell says running scripts is disabled, run this once and try again:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
   (Or use the old Command Prompt instead, where the activate command is `.venv\Scripts\activate.bat`.)
5. **Start the server** (activate first if you opened a new terminal: `.venv\Scripts\Activate.ps1`):
   ```
   python -m trainer
   ```
   It prints two addresses: one for this computer and one for your phone.
   Leave this window open while you drill. Press `Ctrl+C` to stop.
6. **Open it:**
   - On the computer: <http://localhost:8000>
   - On your phone: connect the phone to the **same Wi-Fi** as the computer, then type the
     "phone" address that was printed (it looks like `http://192.168.1.23:8000`) into the
     phone's browser.
   - The first time, Windows may pop up a firewall question for Python. Allow it on
     **Private networks**. If the phone can't connect, that firewall setting is the usual cause
     (Windows Security > Firewall & network protection > Allow an app through firewall > Python).
   - Make sure your Wi-Fi is set as a "Private" network in Windows, not "Public".
   - Tip: on the phone, use "Add to Home Screen" so it opens like an app.

### Running the tests

With the virtual environment activated:
```
python -m pytest
```
All tests should pass. Run them after any change that touches grading or charts.
They take about 30 seconds; the equity tests run thousands of simulated hands on purpose.

## How it's organized

```
trainer/
  game/        cards, positions, hand classes, equity, Omaha nuts, pot-limit math
               (thin layer over PokerKit, no strategy)
  charts/      chart file format: loader + range-string importer
  scenarios/   builds spots: preflop, postflop (board, pot, bet), PLO nuts and pot-limit
  graders/     grades your answer (against a chart, or by computed equity)
  drills/      picks the next spot for a drill (weighted toward your leaks)
  solvers/     the push/fold equilibrium solver
  progress/    SQLite storage of every attempt
  api/         web routes (FastAPI)
  config.py    tunable settings (grading thresholds live here)
data/
  charts/nlhe/          NLHE charts (one JSON file per spot)
  charts/nlhe/sample/   the fake SAMPLE charts (delete this folder once you have real ones)
  charts/pushfold/      computed heads-up push/fold charts (real, not samples)
  equity_cache/         the 169x169 all-in equity table (committed) and a 5-card rank cache
  progress.sqlite       your drill history (created automatically, not in git)
web/           the drill screens: index.html (preflop), equity.html, nuts.html, potlimit.html,
               stats.html, shared common.js / style.css
scripts/       helper scripts (sample chart generator, range importer)
docs/          notes: phase summaries and decisions.md (every judgment call made for you)
tests/         automated tests
```

## The equity drill (phase 2)

You see your hand (2 cards for Hold'em, 4 for Omaha), a flop or turn, the pot, and a bet
you're facing. Your opponent holds **a random hand**. You answer two questions:

1. **Your equity:** your share of the pot if all the cards were dealt out right now. Pick a
   range: under 20%, 20-30, 30-40, 40-50, 50-60, or 60%+.
2. **Call or fold.**

How it's graded:
- The program deals out 2,500 random opponent hands and runouts, and PokerKit decides each
  winner. That gives your equity within about ±1%.
- **Equity needed to call** = call / (pot + bet + call). Example: 50 into a pot of 100 means
  50 / (100 + 50 + 50) = 25%. Calling is right when your equity is at least that.
- Because the simulation is only accurate to about ±1%, an answer within 2 percentage points
  of the line (or of an equity range's edge) is graded **Close enough** instead of Wrong.
- **Direct odds only.** Money you might win on later streets (implied odds) is ignored.

Settings (number of simulated hands, the 2-point tolerance, pot and bet sizes) are in
`trainer/config.py`.

## The PLO drills (phase 3)

**Nuts.** You see a flop, turn or river and your four cards, and answer up to three questions:
1. *What is the nuts right now?* Four hand descriptions, one right.
2. *Do you have it?* Yes or no. Tying the best possible hand counts as yes.
3. *With the next card, are you drawing to the nuts, to a non-nut hand, or neither?* (Flop and
   turn only, and only when you don't already have the nuts.)

How it's graded: the program lists every two-card holding an opponent could have, combines each
with the board under Omaha rules (exactly two hole cards, three board cards), and PokerKit ranks
them. "The nuts" means the best hand *anyone can hold given your cards*: if you hold the ace of
spades, nobody else can make the ace-high flush, and the app tells you when your cards block a
hand like that. "Drawing" looks at the very next card only, and only counts hands of a straight
or better.

**Pot limit.** The blinds and this round's action are shown; you type the biggest total bet you
may make. The rule: you may raise by the size of the pot *after* your call.

```
amount_to_call = largest_bet_this_round - your_chips_already_in_this_round
max_raise_to   = largest_bet_this_round + (pot_including_all_bets + amount_to_call)
```

Example: blinds 1/2, you're first to act: pot 3, call 2, so raise to 2 + (3 + 2) = 7.
Blinds, pot sizes and bet sizes used by the drill are in `trainer/config.py`.

## Tournament push/fold (phase 4)

Short-stack heads-up spots: the small blind (the button) shoves or folds, the big blind calls or
folds. The charts in `data/charts/pushfold/` were **computed by the program**, not copied from
anywhere: a Nash equilibrium by chip EV (no ICM) for equal stacks of 3 to 15 big blinds, with and
without antes. Hand-vs-hand equities come from `data/equity_cache/preflop_equity_169.json`, a
169 x 169 table built by `scripts/build_equity_table.py` (seeded Monte Carlo, 40,000 boards per
matchup, every showdown ranked by PokerKit). Both are committed, so you never need to rebuild
them; `scripts/build_pushfold_charts.py` re-solves the charts in under a minute if you change
the settings in `trainer/config.py`.

In the Preflop filters pick **Format: Tournament** to drill them. Mixed frequencies in these charts
mean the hand is close to indifferent, so either action is graded acceptable. Push/fold at more
than two players is not solved yet (see `docs/decisions.md`).

## Leak tracking (phase 5)

Every answer is stored, and the **Stats** tab breaks accuracy down by drill, position, spot type,
hand category (pairs, suited aces, ...) and format. A category is a *leak* once you've answered it
at least 5 times with a score under 70% (an "acceptable" answer counts half).

The Preflop drill uses this automatically: weak positions, spot types and hand categories come up
more often, and a spot you got wrong comes back after 5 more hands, then at doubling intervals
until you've nailed it. **Drill my leaks** (in the Preflop filters) serves nothing but weak areas
and due reviews.

## Why this hand (phase 9)

Under every Preflop result there is a fold-out "Why this hand?". It describes the hand in plain
words (pair, suited, connected, blockers), gives its all-in equity against a random hand and its
rank among the 169 starting hands (from the computed equity table), and says where it sits in
this chart: how often the chart plays it, how many hands it plays more often, and the weakest
hand of the same kind the chart still plays. Everything is computed from the cards and the chart;
it is a description, not extra advice.

## Real preflop charts (phase 7)

`data/charts/nlhe/pokalab/` holds nine 6-max 100bb charts read straight from
[Pokalab's free preflop charts](https://www.pokalab.com/tools/preflop-charts) (solver output,
opens to 2.5bb, SB to 3bb, GGPoker NL50 rake). They were verified the same way as advice:

1. Both pages were downloaded and the exact per-hand frequencies parsed from the page itself.
2. Sanity checks: premium hands always raise, earlier seats open fewer hands than later ones, nobody
   folds aces to an open.
3. Each chart was compared with [HoldemPro's](https://holdempro.app/tools/preflop-ranges) chart
   for the same spot (simplified solver output). A chart ships only if the two agree on the main
   action for at least 85% of hands; the agreement figures are written into each chart's source
   notes and into `_verification.json`. The big blind vs small blind chart failed (73%) and is not shipped.

`python scripts/import_real_charts.py` repeats the whole process (needs network and Node with
Playwright, because HoldemPro draws its charts with JavaScript). The downloaded pages are kept in
`_pages/` so the import can be audited offline.

## Advice and how it's verified (phase 6)

Result screens can show short tips for the spot you just played. A tip is shown **only** when it
passed the verification standard in `CLAUDE.md`: its sources were actually fetched and the quoted
passage found on the page, at least two unrelated publishers agree, and any math the program can
check agrees too. Every tip has a **Why trust this?** button showing the sources, quotes, check
dates and checks.

- Tips live in `data/advice/tips.json` with a status: `verified` (shown), `contested` (sources or
  math disagree; never shown), `unverified` (not checked yet; never shown).
- `python scripts/verify_tips.py` does the checking: it downloads each source, looks for the
  recorded quote, runs the named math check, and sets the status. It never invents a quote.
- `/api/advice` lists what's verified and what's contested, with evidence.

## Preflop grading

Charts can mix actions (e.g. raise 60%, fold 40%). Your answer is graded by how often the
chart takes the action you picked:

- 50% or more: **Correct**
- 15% to under 50%: **Acceptable (mixed)**
- under 15%: **Wrong**

The thresholds are in `trainer/config.py` (`GRADE_THRESHOLDS`) if you want to change them.

## Chart files

One JSON file per spot, anywhere under `data/charts/`. Example:

```json
{
  "id": "nlhe-cash-6max-100bb-rfi-CO",
  "game": "nlhe",
  "format": "cash",
  "table_size": 6,
  "stack_bb": 100,
  "spot": {"type": "rfi", "hero_pos": "CO", "villain_pos": null, "facing": null},
  "actions": ["fold", "raise_2.5"],
  "source": {"name": "Where this chart came from", "url": "", "notes": ""},
  "hands": {
    "AA": {"raise_2.5": 1.0},
    "A5s": {"raise_2.5": 0.6, "fold": 0.4}
  }
}
```

- Hand keys are the 169 hand classes (`AA`, `AKs`, `AKo`, ... `32o`).
- Frequencies for each hand must add up to 1.0.
- Hands left out count as **fold**, and the app logs a warning listing them.
- Action names: `fold`, `call`, `raise_<size in bb>` (e.g. `raise_2.5` means raise to 2.5bb;
  in a `vs_open` spot this is your 3-bet, in a `vs_3bet` spot your 4-bet), `allin`.
- Spot types: `rfi` (folded to you), `vs_open` (someone opened; `villain_pos` is the opener),
  `vs_3bet` (you opened, `villain_pos` 3-bet you).
- `facing` holds the sizes you're facing so the drill can show them:
  `{"open_size_bb": 2.5}` for `vs_open`, `{"open_size_bb": 2.5, "threebet_size_bb": 9}` for `vs_3bet`.

### Adding real charts (range-string importer)

Most charts are published as range strings like `AA,KK,QQ,AKs,AQs:0.5,A5s:0.6`.
The importer turns those into a chart file. It understands:

| Text | Means |
|---|---|
| `AKs` / `AKo` / `AK` | suited / offsuit / both |
| `22+` | 22 up to AA |
| `A2s+` | A2s up to AKs |
| `KTo+` | KTo, KJo, KQo |
| `22-55`, `A2s-A5s` | everything between, inclusive |
| `AQs:0.5` | this action 50% of the time (also works on shorthand: `A2s+:0.5`) |

Example (one range per non-fold action; whatever is left over becomes fold). Type it as one line:

```
python scripts/import_range.py --id nlhe-cash-6max-100bb-rfi-CO --table-size 6 --type rfi --hero CO --action "raise_2.5=AA,KK,QQ,AKs,AQs:0.5,A5s:0.6" --source-name "My chart source" --out data/charts/nlhe/rfi-6max-CO.json
```

For a `vs_open` or `vs_3bet` chart add `--villain BTN` (and `--open-size 2.5`, `--threebet-size 9`),
and give one `--action` per action, e.g. `--action "call=..." --action "raise_9=..."`.
The importer refuses to write the file if anything in the ranges is unclear (a typo, a hand
listed twice, frequencies adding up to more than 100%), and tells you which hand or token is wrong.

The app loads charts when it starts, so restart the server after adding or changing chart files.
If a chart file has a mistake, the server won't start and the message names the file and the problem.

**When you add real charts:** delete the `data/charts/nlhe/sample/` folder (or keep it, but then
sample spots stay mixed into your drills). Two charts for the exact same spot aren't allowed.

Run `python scripts/import_range.py --help` for all options.
