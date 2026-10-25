"""Write docs/glossary.md from web/glossary.json (the app's single source of truth)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "glossary.json"
OUT = ROOT / "docs" / "glossary.md"


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    lines = ["# Glossary", "",
             "Plain-language meanings of the poker words used in the app. Definitions only, no strategy.",
             "The app underlines these words; tap one for its meaning. Edit `web/glossary.json` and run",
             "`python scripts/export_glossary.py` to update this file.", ""]
    for g in data["groups"]:
        lines += [f"## {g['title']}", ""]
        for t in sorted(g["terms"], key=lambda t: t["term"].lower()):
            also = f" *(also: {', '.join(t['aliases'])})*" if t.get("aliases") else ""
            lines.append(f"- **{t['term']}**{also}: {t['definition']}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({sum(len(g['terms']) for g in data['groups'])} terms)")


if __name__ == "__main__":
    main()
