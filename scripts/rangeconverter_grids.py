"""Read the chart grids out of RangeConverter's free 9-max 100bb PDF.

    python scripts/rangeconverter_grids.py <pdf> <out.json>

Needs poppler's  on the PATH and Requirement already satisfied: pillow in /usr/local/lib/python3.13/dist-packages (12.3.0)
Collecting scipy
  Using cached scipy-1.18.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (62 kB)
Requirement already satisfied: numpy<2.8,>=2.0.0 in /usr/local/lib/python3.13/dist-packages (from scipy) (2.5.3)
Using cached scipy-1.18.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (35.3 MB)
Installing collected packages: scipy
Successfully installed scipy-1.18.1 (not app
dependencies; this is an import-time tool). Nothing is typed from memory: every
frequency is read from the drawn grids, and scripts/import_rangeconverter.py
checks the totals against the percentages printed on the charts.

The grids are 13x13 hand squares drawn in flat colours:

blue = fold, orange = raise, green = call, red = all-in, dark = hand not in play here.
Mixed cells are split vertically (half orange, half blue = raise 50% / fold 50%).

Method: find every coloured square as a connected component, cluster touching squares,
anchor each grid on its top-left square (AA, always in play), measure the cell pitch,
then read all 169 cells by position and record the share of each colour across the
cell's width.
"""
import sys, json
from PIL import Image
import numpy as np
from scipy import ndimage

PALETTE = {"fold": (32,120,160), "raise": (224,128,16), "call": (64,144,104), "allin": (160,16,24)}
RANKS = "AKQJT98765432"

def masks_for(a):
    return {k: np.abs(a - np.array(c)).sum(axis=2) < 60 for k, c in PALETTE.items()}

# The PDF uses two page layouts. Cell pitches measured on the dense RFI / facing-open pages
# (first and last cell edges over 12 cells): 4-across pages 35.0 x 38.67 px, 3-across pages
# 38.0 x 42.08 px. A page's layout is recognised from the gap between adjacent coloured cells.
DARKS = [(18, 38, 60), (45, 58, 68)]   # never-in-play, and the not-opened share of a partly-opened hand; page background is about (8, 26, 54)
LAYOUTS = [(35.0, 38.67), (38.0, 42.08)]

def frames(a, masks, dilate=7):
    """A grid's coloured cells form one blob once small gaps are closed; the blob's top-left
    corner is the AA cell (always in play). The pitch comes from the page layout."""
    anym = np.zeros_like(next(iter(masks.values())))
    for m in masks.values(): anym |= m
    blob = ndimage.binary_dilation(anym, iterations=dilate)
    lab, n = ndimage.label(blob)
    out = []
    def run_starts(prof):
        st = [i for i in range(1, len(prof)) if prof[i] and not prof[i - 1]]
        return ([0] + st) if prof[0] else st
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        ys, xs = np.nonzero(anym[sl] & (lab[sl] == i))
        if len(xs) == 0: continue
        x0, x1 = int(xs.min()) + sl[1].start, int(xs.max()) + sl[1].start
        y0, y1 = int(ys.min()) + sl[0].start, int(ys.max()) + sl[0].start
        if x1 - x0 < 150 or y1 - y0 < 100:   # legend bars and stray bits
            continue
        st = run_starts(anym[y0 + 2:y0 + 6, x0:x0 + 13 * 48].mean(axis=0) > 0.5)
        d = np.diff(st); d = d[(d >= 25) & (d <= 70)]
        if len(d) < 1:
            continue
        rough = float(np.median(d))
        px, py = min(LAYOUTS, key=lambda L: abs(L[0] - rough))
        out.append({"left": x0, "top": y0, "pitch": px, "vpitch": py, "size": px - 2})
    # drop blobs that are a disconnected part of a grid found further up/left
    keep = []
    for f in out:
        inside = any(g is not f and g["left"] - 5 <= f["left"] < g["left"] + 13 * g["pitch"]
                     and g["top"] - 5 <= f["top"] < g["top"] + 13 * g["vpitch"]
                     and (g["top"], g["left"]) < (f["top"], f["left"]) for g in out)
        if not inside: keep.append(f)
    keep.sort(key=lambda f: (round(f["top"] / 300), f["left"]))
    return keep

def read_cell(a, masks, dark, x0, y0, px, py):
    """Classify every pixel inside the cell (3px margin). Dark area = share of this hand
    not in play here; coloured area is split between the actions. White text is ignored."""
    x0, y0 = int(round(x0)), int(round(y0))
    sl = (slice(y0 + 2, y0 + int(round(py)) - 1), slice(x0 + 2, x0 + int(round(px)) - 2))
    counts = {k: int(m[sl].sum()) for k, m in masks.items()}
    n_col = sum(counts.values()); n_dark = int(dark[sl].sum())
    if n_col + n_dark < 0.3 * (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start):
        return None
    if n_col < 0.03 * (n_col + n_dark):
        return None
    out = {k: round(v / n_col, 3) for k, v in counts.items() if v / n_col >= 0.02}
    out["_in_play"] = round(n_col / (n_col + n_dark), 3)
    return out

def hand_name(r, c):
    if r == c: return RANKS[r] * 2
    if c > r: return RANKS[r] + RANKS[c] + "s"
    return RANKS[c] + RANKS[r] + "o"

def combos(h): return 6 if len(h) == 2 else (4 if h[2] == "s" else 12)

def summary(hands):
    tot = {}; n = 0
    for h, f in hands.items():
        if f is None: continue
        w = combos(h) * f["_in_play"]; n += w
        for k, v in f.items():
            if k != "_in_play": tot[k] = tot.get(k, 0) + v * w
    return {k: round(100 * v / n, 2) for k, v in sorted(tot.items())}, round(100 * n / 1326, 2)

def parse_page(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    masks = masks_for(a)
    dark = np.zeros(a.shape[:2], bool)
    for d in DARKS: dark |= np.abs(a - np.array(d)).sum(axis=2) < 12
    fr = frames(a, masks)
    out = []
    for f in fr:
        hands = {}
        for r in range(13):
            for c in range(13):
                hands[hand_name(r, c)] = read_cell(a, masks, dark, f["left"] + c * f["pitch"], f["top"] + r * f["vpitch"], f["pitch"], f["vpitch"])
        out.append({**f, "hands": hands})
    return out


PAGE_SECTIONS = [  # image index in the PDF -> what the page shows (the PDF's text layer lists the sections in this order)
    ("rfi", None), ("vs_open", "EPMP"), ("vs_open", "LJ"), ("vs_open", "HJ"), ("vs_open", "CO"),
    ("vs_open", "BTN"), ("vs_open", "SB"), ("vs_open", "BB"),
    ("vs_3bet", "UTG"), ("vs_3bet", "UTG1"), ("vs_3bet", "MP"), ("vs_3bet", "LJ"), ("vs_3bet", "HJ"),
    ("vs_3bet", "CO"), ("vs_3bet", "BTN"), ("vs_3bet", "SB"),
]


def main(argv):
    import hashlib, subprocess, tempfile, os
    pdf, out = argv[1], argv[2]
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdfimages", "-png", pdf, os.path.join(tmp, "p")], check=True)
        pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        # chart pages are the RGB images of 2048x1313; every odd index is a mask, index 0 the banner
        pages = []
        for f in pngs:
            im = Image.open(os.path.join(tmp, f))
            if im.size == (2048, 1313) and im.mode == "RGB":
                pages.append(os.path.join(tmp, f))
        if len(pages) != len(PAGE_SECTIONS):
            raise SystemExit(f"expected {len(PAGE_SECTIONS)} chart pages, found {len(pages)}")
        result = {"pdf_sha256": sha, "pages": []}
        for path, (spot, section) in zip(pages, PAGE_SECTIONS):
            grids = parse_page(path)
            for g in grids:
                g["shares"], g["in_play_pct"] = summary(g["hands"])
            result["pages"].append({"image": os.path.basename(path), "spot_type": spot, "section": section, "grids": grids})
            print(f"{os.path.basename(path)} {spot} {section}: {len(grids)} grids")
    json.dump(result, open(out, "w"), indent=0)


if __name__ == "__main__":
    main(sys.argv)
