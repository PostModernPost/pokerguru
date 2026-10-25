# Phase 1 summary (for Adam's review)

## What was built

A preflop trainer for NLHE cash games, 6-max and 9-handed, 100bb.

- **Drill screen:** table size, stack depth, spot type, a strip showing every seat (folded,
  raised, you, still to act), the action so far, pot and amount to call, your two cards, and
  one big button per action.
- **Result screen:** Correct / Acceptable (mixed) / Wrong, the chart's frequencies for your
  hand, a one-sentence explanation built from the chart, the full 13x13 range with your hand
  outlined, and where the chart came from.
- **Filters:** table size, your position, spot type. Your choices are remembered on that device.
- **History:** every answer is saved to `data/progress.sqlite`, including response time, which
  phase 5 (leak tracking) will use.
- **Range importer:** `scripts/import_range.py` turns range text like `AA,KK,AQs:0.5,A2s+`
  into a chart file.
- **Tests:** 170 automated tests, passing on Python 3.11 and 3.13. Run them with `python -m pytest`.

Start the app with `python -m trainer`. The README walks through the Windows setup.

## Decisions made without asking

1. **The sample charts are random noise.** The brief says never to invent strategy, so instead
   of writing plausible-looking ranges, I had a script fill them with random frequencies from a
   fixed seed. They're useless for learning, which is the point: nobody can mistake them for
   advice. A red banner shows whenever one is used. They live in `data/charts/nlhe/sample/`.
   Delete that folder once you have real charts.
2. **Placeholder bet sizes in the samples:** open 2.5bb, 3-bet 8bb, 4-bet 20bb. These are only
   labels on fake data. Real charts carry their own sizes (see open questions).
3. **How bet sizes are stored.** The action names in a chart give *your* size (`raise_2.5` means
   raise to 2.5bb). The sizes you're *facing* go in the chart's `spot.facing` field as
   `{"open_size_bb": 2.5}` or `{"open_size_bb": 2.5, "threebet_size_bb": 8}`. The brief left
   `facing` undefined, so this format is my choice.
4. **A raise is called `raise_<size>` in every spot type.** The screen labels it by context:
   "Raise to 2.5bb" when you're first in, "3-bet to 8bb" facing an open, "4-bet to 20bb"
   facing a 3-bet.
5. **The range importer is strict.** If the same hand appears twice in one range (for example
   `A2s+,A5s:0.6`), it stops with an error instead of guessing which one wins, because different
   chart tools resolve that differently. It also accepts `22-55` / `A2s-A5s` spans and `50%`
   as well as `0.5`. Specific card combos like `AsKs` are rejected, since charts are by hand class.
6. **Hands are dealt at random.** Each hand class shows up as often as it would at a real table.
   Pairs come up rarely and trash hands that are easy folds come up a lot. Phase 5 will steer
   this toward your weak spots.
7. **The loader is strict too.** A chart with a mistake (frequencies that don't add to 1, an
   unknown hand or action, or an impossible spot like "BB raises first in") stops the server
   with a message naming the file. Missing hands are the one exception: as the brief says, they
   count as fold, with a warning in the server window. Rounding slack of ±0.001 is allowed when
   checking that frequencies add up to 1, because published charts are often rounded.
8. **Exact grading boundaries:** exactly 50% counts as Correct and exactly 15% as Acceptable.
   You can change the thresholds in `trainer/config.py`.
9. **Four-colour deck** (spades black, hearts red, diamonds blue, clubs green), so suits are
   easy to tell apart on a phone.
10. **Two small libraries beyond the brief's list:** `uvicorn`, which actually runs the FastAPI
    server, and `httpx`, which FastAPI's test tool needs. Neither one changes the stack.
    All versions are pinned in `requirements.txt`.
11. **The server keeps no memory of the question on screen.** The phone sends back the chart ID
    and cards with your answer. If the server restarts mid-hand, nothing is lost.
12. **Chart code location:** the loader and importer live in `trainer/charts/`, a folder the
    brief's suggested layout didn't include.

## Things I was unsure about

- **PokerKit's online docs site** (readthedocs) was unreachable from my environment. I checked
  the API against PokerKit 0.7.7's own source code and docs files on GitHub, and ran each
  function to make sure it works. Phase 1 only uses PokerKit's cards and deck. Hand evaluation
  and equity are checked and noted in the README for phase 2.
- **Antes:** the scenario code accepts an ante, but phase 1 cash spots have none.
- **The "everyone acts once" assumption:** vs_open spots assume everyone between the opener and
  you folded, and vs_3bet spots assume only the 3-bettor stayed in. No cold-callers or squeezes.
  That matches the three spot types in the brief.

## Open questions for you (from the brief)

1. Which chart sources should we use for NLHE cash? Until you supply them, the app has only
   sample charts.
2. What open-raise (and 3-bet / 4-bet) sizes do you want to drill, for 6-max online and for
   9-handed live?
3. Does your chart source have different versions for different rake levels?
4. Should we add 40bb or 200bb stacks later?
