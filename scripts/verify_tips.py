"""Verify the advice library against its sources, then record the results.

    python scripts/verify_tips.py            # check every tip, update statuses
    python scripts/verify_tips.py --only pot-odds-formula

For each source URL the script downloads the page, strips the HTML, and
looks for the recorded quote (whitespace and quote marks normalised). It
records the access date, writes 'source_fetched' and 'corroborated' checks,
runs any math check named in the tip's "math_check" field, and sets the
status: 'verified' when everything passes; 'contested' when the sources and
the math disagree; 'single_source' when only one publisher confirmed it
(both shown in the app with a footnote); 'unverified' when nothing could be
confirmed (page unreachable, quote not found), which is never shown. It never invents a quote: a
source with an empty quote can only ever be 'unverified'.

Needs network access to the source sites.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trainer.advice import math_checks  # noqa: E402
from trainer.advice.library import MIN_INDEPENDENT_SOURCES, TIPS_PATH, tip_from_dict  # noqa: E402

UA = "Mozilla/5.0 (poker-trainer verify_tips; +https://github.com/postmodernpost/pokerguru)"


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    return normalise(html.unescape(text))


def normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    # HTML stripping leaves spaces before punctuation ("AKs , is"); ignore those on both sides.
    text = re.sub(r" ([,.;:!?)])", r"\1", text)
    return text.strip().lower()


def check_tip(tip: dict, today: str) -> dict:
    checks = []
    fetched_ok = 0
    for src in tip["sources"]:
        quote = normalise(src.get("quote", ""))
        try:
            page = fetch_text(src["url"])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            checks.append({"type": "source_fetched", "passed": False, "detail": f"{src['url']}: could not fetch ({e})"})
            continue
        if not quote:
            checks.append({"type": "source_fetched", "passed": False,
                           "detail": f"{src['url']}: fetched, but no quote recorded yet (record the exact passage)"})
            continue
        if quote in page:
            src["accessed"] = today
            fetched_ok += 1
            checks.append({"type": "source_fetched", "passed": True, "detail": f"{src['url']}: quote found on page {today}"})
        else:
            checks.append({"type": "source_fetched", "passed": False,
                           "detail": f"{src['url']}: fetched, but the recorded quote was not found on the page"})
    publishers = {s["publisher"].strip().lower() for s, c in zip(tip["sources"], checks) if c["passed"]}
    corroborated = len(publishers) >= MIN_INDEPENDENT_SOURCES
    checks.append({"type": "corroborated", "passed": corroborated,
                   "detail": f"{len(publishers)} independent publisher(s) confirmed (need {MIN_INDEPENDENT_SOURCES})"})
    if tip.get("math_check"):
        ok, detail = math_checks.run(tip["math_check"])
        checks.append({"type": "math_consistent", "passed": ok, "detail": detail})
    tip["checks"] = checks
    math_failed = any(c["type"] == "math_consistent" and not c["passed"] for c in checks)
    if all(c["passed"] for c in checks):
        tip["status"] = "verified"
    elif math_failed:
        tip["status"] = "contested"  # a source and the math disagree: shown with a footnote
    elif fetched_ok >= 1:
        tip["status"] = "single_source"  # one publisher confirmed: shown with a footnote
    else:
        tip["status"] = "unverified"  # nothing confirmed (page unreachable, quote not found): hidden
    return tip


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="tip id to check")
    p.add_argument("--path", default=str(TIPS_PATH))
    args = p.parse_args()
    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    summary = {"verified": 0, "single_source": 0, "contested": 0, "unverified": 0}
    for tip in data["tips"]:
        if args.only and tip["id"] != args.only:
            continue
        check_tip(tip, today)
        tip_from_dict(tip)  # make sure the result still satisfies the loader's rules
        summary[tip["status"]] += 1
        print(f"{tip['status']:10s} {tip['id']}")
        for c in tip["checks"]:
            if not c["passed"]:
                print(f"           - {c['type']}: {c['detail']}")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
