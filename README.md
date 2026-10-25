# Poker Trainer

A drill-based trainer for No-Limit Hold'em (and later Pot-Limit Omaha). It shows you a
spot, you pick an action, and it grades you right away against an answer key (a chart file).

**Current status: Phase 1 (NLHE cash preflop trainer).** The only charts included are
**SAMPLE charts with random made-up frequencies**. They exist to test the app. They are
**not real strategy** and the app shows a red warning whenever one is in use. Add your own
charts (see "Adding real charts" below) before you drill for real.

## Built with

| Piece | Version | What it does |
|---|---|---|
| Python | 3.11 or newer | the language |
| [PokerKit](https://github.com/uoftcprg/pokerkit) | **0.7.7** | cards, dealing, hand evaluation, equity |
| FastAPI + uvicorn | 0.162 / 0.54 | the web server |
| SQLite | built into Python | stores every drill attempt |
| pytest | 9.1 | tests |

PokerKit API checked against version 0.7.7 (source and docs) before use:
- Cards: `Card.parse("AsKd")`, `Deck.STANDARD` (52 cards), each card has `.rank` and `.suit`.
- Hand evaluation (for later phases): `StandardHighHand.from_game(hole, board)` for Hold'em,
  `OmahaHoldemHand.from_game(hole, board)` for Omaha (exactly 2 hole + 3 board cards).
- Equity (for later phases): `calculate_equities(hole_ranges, board_cards, hole_dealing_count,
  board_dealing_count, deck, hand_types, *, sample_count=..., executor=None)` with
  `parse_range("AK")` for ranges.

Phase 1 only uses the card and deck parts.

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

## How it's organized

```
trainer/
  game/        cards, positions, hand classes (thin layer over PokerKit, no strategy)
  charts/      chart file format: loader + range-string importer
  scenarios/   builds a preflop spot (positions, action so far, pot) from parameters
  graders/     grades your answer against a chart
  drills/      picks the next spot for a drill
  progress/    SQLite storage of every attempt
  api/         web routes (FastAPI)
  config.py    tunable settings (grading thresholds live here)
data/
  charts/nlhe/          NLHE charts (one JSON file per spot)
  charts/nlhe/sample/   the fake SAMPLE charts (delete this folder once you have real ones)
  progress.sqlite       your drill history (created automatically, not in git)
web/           the drill screens (HTML, CSS, JavaScript)
scripts/       helper scripts (sample chart generator, range importer)
docs/          notes, including the phase 1 summary and open questions
tests/         automated tests
```

## Grading

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
