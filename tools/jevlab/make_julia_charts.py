#!/usr/bin/env python3
"""Charts + flowcharts for the Julia-1 blog sequel (docs/jevlab/BLOG-SEQUEL.md).

Run:  /tmp/chartvenv/bin/python tools/jevlab/make_julia_charts.py

Numbers come from the frozen run files on the lab laptop
(slim:~/julia-bakeoff/fair-runs/*_rows.jsonl) and Tasks Docs #1423 / #1424.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, Polygon

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "jevlab" / "illustrations" / "julia"
OUT.mkdir(parents=True, exist_ok=True)

for name in ("Regular", "Medium", "SemiBold", "Bold"):
    p = Path(f"/tmp/chartvenv/Inter-{name}.ttf")
    if p.exists():
        fm.fontManager.addfont(str(p))

BG = "#F7F8FA"
CARD = "#FFFFFF"
INK = "#1A2332"
MUTED = "#5B6B7C"
RULE = "#D8DEE6"
FLY = "#4A5D75"
JEV = "#2A2D33"
LAYA = "#8FA5BC"
JULIA = "#C8553D"
JULIA_SOFT = "#F3D9D2"
GOOD = "#3F7D5C"

plt.rcParams.update({
    "font.family": "Inter",
    "text.color": INK,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

MODELS = [("Julia-1", JULIA), ("Jev (hosted)", JEV), ("Laya (on-prem)", LAYA), ("Flybrain", FLY)]


def title_block(fig, title, subtitle=None):
    fig.text(0.04, 0.955, title, fontsize=16, fontweight="bold", color=INK, ha="left", va="top")
    if subtitle:
        fig.text(0.04, 0.895, subtitle, fontsize=10.5, color=MUTED, ha="left", va="top")


def brand(fig, note=None):
    fig.text(0.96, 0.025, "Decision Science Corp", fontsize=8, color=MUTED, ha="right", va="bottom")
    if note:
        fig.text(0.04, 0.025, note, fontsize=8.5, color=MUTED, ha="left", va="bottom")


def save(fig, name):
    path = OUT / name
    fig.savefig(path, dpi=160, facecolor=BG)
    plt.close(fig)
    print("wrote", path)


def grouped_bars(ax, tests, values, hatched=None, width=0.2):
    hatched = hatched or set()
    for mi, (label, color) in enumerate(MODELS):
        for ti, _ in enumerate(tests):
            v = values[mi][ti]
            if v is None:
                continue
            x = ti + (mi - 1.5) * width
            ax.bar(x, v, width, color=color, edgecolor=BG if (mi, ti) not in hatched else "white",
                   hatch="///" if (mi, ti) in hatched else None, linewidth=0.6,
                   label=label if ti == 0 or (mi == 0 and values[0][0] is None) else None)
            ax.text(x, v + 1.2, f"{int(v + 0.5)}", ha="center", va="bottom", fontsize=8.5,
                    color=JULIA if mi == 0 else MUTED, fontweight="bold" if mi == 0 else "regular", zorder=7,
                    bbox=dict(facecolor=BG, edgecolor="none", pad=0.6, alpha=0.9))


# ---------------------------------------------------------------- 1. hero
def hero_card_vs_full():
    fig = plt.figure(figsize=(11, 6.2), facecolor=BG)
    title_block(fig, "Julia-1: what the model card says vs. what the full test set says",
                "Same published weights. Their headline number vs. our run on the complete public test set.")
    ax = fig.add_axes([0.24, 0.14, 0.50, 0.68], facecolor=BG)
    rows = [
        ("AG News", "news topics", 94.0, 85.1, "Card: 100-row sample\nUs: all 7,600 rows", MUTED),
        ("Emotion", "six moods", 86.0, 79.9, "Card: 100-row sample\nUs: all 2,000 rows", MUTED),
        ("MASSIVE", "voice commands", 86.75, 50.4, "Menu wording never published.\nSame 2,974 rows: 50%", JULIA),
        ("Typed-decisions", "full recipe public", 72.55, 72.55, "Full recipe published.\nExact match.", GOOD),
    ]
    for i, (name, sub, card, ours, note, col) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([ours, card], [y, y], color=col, lw=3, alpha=0.55, solid_capstyle="round", zorder=1)
        ax.scatter([card], [y], s=160, facecolor=BG, edgecolor=INK, linewidth=2, zorder=3)
        ax.scatter([ours], [y], s=160, color=col if col != MUTED else JULIA, zorder=4)
        if abs(card - ours) > 0.5:
            ax.text(card + 1.2, y + 0.2, f"card {card:g}%", fontsize=9, color=INK, va="bottom", ha="left")
            ax.text(ours - 1.2, y + 0.2, f"ours {ours:g}%", fontsize=9, color=JULIA, fontweight="bold",
                    va="bottom", ha="right")
        else:
            ax.text(ours, y + 0.22, f"card {card:g}% = ours {ours:g}%", fontsize=9, color=GOOD,
                    fontweight="bold", va="bottom", ha="center")
        fig.text(0.04, 0.14 + 0.68 * (y + 0.5) / len(rows) + 0.012, name, fontsize=12, fontweight="bold",
                 color=INK, va="center")
        fig.text(0.04, 0.14 + 0.68 * (y + 0.5) / len(rows) - 0.03, sub, fontsize=9.5, color=MUTED, va="center")
        fig.text(0.77, 0.14 + 0.68 * (y + 0.5) / len(rows), note, fontsize=9.5,
                 color=col if col != MUTED else INK, va="center", linespacing=1.4)
    ax.set_ylim(-0.5, len(rows) - 0.5)
    ax.set_xlim(40, 100)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Accuracy (%)", fontsize=10, color=MUTED)
    ax.grid(axis="x", color=RULE, lw=0.6)
    ax.set_axisbelow(True)
    ax.scatter([], [], s=90, facecolor=BG, edgecolor=INK, linewidth=2, label="Model card claim")
    ax.scatter([], [], s=90, color=JULIA, label="Our run, full test set")
    ax.legend(loc="lower left", frameon=False, fontsize=9, bbox_to_anchor=(0.0, 1.0), ncol=2)
    brand(fig)
    save(fig, "julia-card-vs-full-set.png")


# ---------------------------------------------------------------- 2. round one
def round_one():
    fig = plt.figure(figsize=(11, 6.2), facecolor=BG)
    title_block(fig, "Round one: Julia-1 on the shared scoreboard",
                "Same four tests, same rows as last week's bakeoff. Dashed line = what random picking scores.")
    ax = fig.add_axes([0.07, 0.17, 0.90, 0.64], facecolor=BG)
    tests = ["Movie-review sentiment\n2 options · random 50%", "Ten phone intents\n10 options · random 10%",
             "Bug severity from titles\n3 options · random 33%", "150 intents + none\n151 options · random <1%"]
    values = [
        [57.0, 56.3, 27.7, None],
        [94.6, 99.3, 49.1, 91.7],
        [90.6, 97.3, 29.5, 60.6],
        [76.5, 94.7, 78.4, 64.6],
    ]
    grouped_bars(ax, tests, values, hatched={(1, 3)})
    for ti, chance in enumerate([50.0, 10.0, 100 / 3, 100 / 151]):
        ax.plot([ti - 0.42, ti + 0.42], [chance, chance], ls=(0, (4, 3)), color=INK, lw=1.1, zorder=5)
    ax.text(3 - 0.3, 4, "Julia can't take a menu this long", fontsize=8.5, color=JULIA, ha="center",
            va="bottom", rotation=90)
    ax.set_xticks(range(len(tests)))
    ax.set_xticklabels(tests, fontsize=9.5, color=INK)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Accuracy (%)", fontsize=10)
    ax.grid(axis="y", color=RULE, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=4, bbox_to_anchor=(1.0, 1.1))
    brand(fig, "Hatched: Jev finished 4,060 of 5,500 rows before the hosted API stopped answering.")
    save(fig, "julia-round-one.png")


# ---------------------------------------------------------------- 3. round two
def round_two():
    fig = plt.figure(figsize=(11, 6.2), facecolor=BG)
    title_block(fig, "Round two: Julia-1's own benchmarks, full test sets",
                "Every benchmark its model card claims as a win. Outlined box = the number on the card.")
    ax = fig.add_axes([0.07, 0.17, 0.90, 0.64], facecolor=BG)
    tests = ["AG News\n7,600 headlines", "Emotion\n2,000 posts", "MASSIVE (English)\n2,974 commands",
             "Typed-decisions\n2,000 questions"]
    values = [
        [85.1, 79.9, 50.4, 72.55],
        [88.4, 59.0, 79.1, 74.1],
        [92.9, 59.3, 57.5, 36.2],
        [88.3, 57.7, 81.9, 29.1],
    ]
    grouped_bars(ax, tests, values, hatched={(3, 3)})
    width = 0.2
    for ti, card in enumerate([94.0, 86.0, 86.75, 72.55]):
        x = ti - 1.5 * width
        ax.bar(x, card, width, facecolor="none", edgecolor=JULIA, ls=(0, (3, 2)), lw=1.4, zorder=6)
        if abs(card - values[0][ti]) > 0.5:
            ax.text(x, card + 1.2, f"card\n{card:g}", ha="center", va="bottom", fontsize=8, color=JULIA,
                    linespacing=1.1)
    ax.set_xticks(range(len(tests)))
    ax.set_xticklabels(tests, fontsize=9.5, color=INK)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Accuracy (%)", fontsize=10)
    ax.grid(axis="y", color=RULE, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=4, bbox_to_anchor=(1.0, 1.1))
    brand(fig, "Hatched: typed-decisions has no practice examples, so Flybrain ran it cold.")
    save(fig, "julia-round-two.png")


# ---------------------------------------------------------------- 4. emotion gap
def emotion_gap():
    fig = plt.figure(figsize=(10, 6), facecolor=BG)
    title_block(fig, "Emotion: the gap on the card vs. the gap at full size",
                "Julia-1 vs. Jev. The card scored 100 rows. We scored all 2,000.")
    ax = fig.add_axes([0.14, 0.12, 0.62, 0.70], facecolor=BG)
    xs = [0, 1]
    julia = [86.0, 79.9]
    jev = [48.0, 59.0]
    ax.plot(xs, julia, color=JULIA, lw=3, marker="o", ms=11)
    ax.plot(xs, jev, color=JEV, lw=3, marker="o", ms=11)
    for x, v in zip(xs, julia):
        ax.text(x + (-0.06 if x == 0 else 0.06), v, f"{v:g}%", color=JULIA, fontsize=12, fontweight="bold",
                ha="right" if x == 0 else "left", va="center")
    for x, v in zip(xs, jev):
        ax.text(x + (-0.06 if x == 0 else 0.06), v, f"{v:g}%", color=JEV, fontsize=12, fontweight="bold",
                ha="right" if x == 0 else "left", va="center")
    ax.annotate("", xy=(0, 48), xytext=(0, 86), arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1))
    ax.annotate("", xy=(1, 59), xytext=(1, 79.9), arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1))
    ax.text(0.03, 67, "38-point lead", fontsize=10.5, color=INK, ha="left", va="center")
    ax.text(0.97, 69.5, "21-point lead", fontsize=10.5, color=INK, ha="right", va="center")
    ax.set_xticks(xs)
    ax.set_xticklabels(["Their card\n100 rows", "Our run\nall 2,000 rows"], fontsize=11, color=INK)
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(40, 95)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    fig.text(0.80, 0.62, "Julia-1", color=JULIA, fontsize=13, fontweight="bold")
    fig.text(0.80, 0.33, "Jev", color=JEV, fontsize=13, fontweight="bold")
    fig.text(0.80, 0.20, "Still a real win.\nJust a bit over half\nthe lead the card claims.", color=MUTED, fontsize=10,
             linespacing=1.4)
    brand(fig)
    save(fig, "julia-emotion-gap.png")


# ---------------------------------------------------------------- 5. emotion by label
def emotion_by_label():
    fig = plt.figure(figsize=(11, 6.2), facecolor=BG)
    title_block(fig, "Emotion, mood by mood",
                "Julia-1 wins five of six moods. Sadness, the second-biggest slice of the test, is its worst.")
    ax = fig.add_axes([0.07, 0.17, 0.90, 0.62], facecolor=BG)
    labels = ["anger\n275 rows", "fear\n224 rows", "joy\n695 rows", "love\n159 rows", "sadness\n581 rows",
              "surprise\n66 rows"]
    values = [
        [98.5, 82.1, 87.3, 89.3, 57.5, 90.9],
        [48.0, 52.2, 63.0, 29.6, 72.5, 36.4],
        [45.1, 33.0, 70.4, 32.7, 73.5, 30.3],
        [34.2, 31.2, 82.4, 8.2, 69.0, 3.0],
    ]
    ax.axvspan(3.55, 4.45, color=JULIA_SOFT, zorder=0)
    grouped_bars(ax, labels, values)
    ax.text(4, 101, "Every other model\nbeats Julia here", fontsize=9.5, color=JULIA, ha="center", va="bottom",
            fontweight="bold", linespacing=1.3)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9.5, color=INK)
    ax.set_ylim(0, 118)
    ax.set_ylabel("Accuracy (%)", fontsize=10)
    ax.grid(axis="y", color=RULE, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=4, bbox_to_anchor=(0.0, 1.1))
    brand(fig)
    save(fig, "julia-emotion-by-mood.png")


# ---------------------------------------------------------------- flowchart helpers
def box(ax, x, y, w, h, text, face=CARD, edge=RULE, color=INK, size=10.5, weight="regular", lw=1.2):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                facecolor=face, edgecolor=edge, linewidth=lw))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color=color, fontweight=weight,
            linespacing=1.45)


def diamond(ax, x, y, w, h, text, size=10.5):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True,
                         facecolor="#EEF2F6", edgecolor=MUTED, linewidth=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color=INK, fontweight="semibold",
            linespacing=1.35)


def arrow(ax, x0, y0, x1, y1, label=None, lx=None, ly=None, color=MUTED, ha="center"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3, shrinkA=0, shrinkB=0,
                                mutation_scale=14))
    if label:
        ax.text(lx if lx is not None else (x0 + x1) / 2, ly if ly is not None else (y0 + y1) / 2, label,
                fontsize=9.5, color=INK, ha=ha, va="center", fontweight="semibold",
                bbox=dict(facecolor=BG, edgecolor="none", pad=1.5))


def flow_axes(fig):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return ax


# ---------------------------------------------------------------- 6. card check flow
def card_check_flow():
    fig = plt.figure(figsize=(11, 7.4), facecolor=BG)
    ax = flow_axes(fig)
    title_block(fig, "Checking Julia-1's model card",
                "Where Supersonic published the whole recipe, the number held up. Where they didn't, it didn't.")
    box(ax, 0.5, 0.79, 0.52, 0.075, "Every benchmark Julia-1's model card claims as a win", weight="semibold")
    arrow(ax, 0.5, 0.752, 0.5, 0.705)
    box(ax, 0.5, 0.668, 0.52, 0.075, "Rerun on the complete public test set, same published weights")
    arrow(ax, 0.5, 0.63, 0.5, 0.585)
    diamond(ax, 0.5, 0.51, 0.34, 0.15, "What did they publish\nwith the number?")

    cols = [
        (0.17, "Full test set\nand the prompts", "Typed-decisions\ncard 72.55%\nours 72.55%", "Holds up", GOOD),
        (0.5, "Only a\n100-row sample", "AG News  94% → 85.1%\nEmotion  86% → 79.9%", "Shrinks at full size",
         MUTED),
        (0.83, "Number, but not the\nmenu wording", "MASSIVE\ncard 86.75%\nours 50.4%", "Can't be reproduced",
         JULIA),
    ]
    for x, branch, result, verdict, col in cols:
        if x == 0.5:
            arrow(ax, 0.5, 0.435, 0.5, 0.33, branch, ly=0.385)
        else:
            sx = 0.33 if x < 0.5 else 0.67
            ax.plot([sx, x], [0.51, 0.51], color=MUTED, lw=1.3)
            arrow(ax, x, 0.51, x, 0.33, branch, ly=0.425)
        box(ax, x, 0.255, 0.27, 0.15, result, size=10.5)
        box(ax, x, 0.105, 0.27, 0.07, verdict, face=col if col != MUTED else "#E4E9EF",
            edge=col if col != MUTED else RULE, color="white" if col != MUTED else INK, weight="bold", size=11)
        arrow(ax, x, 0.18, x, 0.14)
    brand(fig)
    save(fig, "julia-card-check-flow.png")


# ---------------------------------------------------------------- 7. which model
def which_model_flow():
    fig = plt.figure(figsize=(11, 8), facecolor=BG)
    ax = flow_axes(fig)
    title_block(fig, "Which decision model for which job",
                "What the two bakeoffs say, as a routing chart.")
    qx, rx = 0.33, 0.78
    qs = [
        (0.78, "Tagging short text\nby mood, CPU only?", "Julia-1", "80% on Emotion vs. 59%\nfor the rest of the field",
         JULIA),
        (0.60, "Menu longer than\nabout twenty options?", "Jev, or long-window Laya",
         "Julia tops out around twenty", JEV),
        (0.42, "Labeled examples, and either thin\ntext or millisecond answers?", "Flybrain",
         "78% on bug titles vs. 49% and 30%.\nA few milliseconds a row", FLY),
        (0.24, "Has to run on\nyour own hardware?", "Laya", "Won AG News at 93%", LAYA),
    ]
    for i, (y, q, pick, why, col) in enumerate(qs):
        diamond(ax, qx, y, 0.36, 0.12, q, size=9.8)
        arrow(ax, qx + 0.18, y, rx - 0.17, y, "yes", lx=(qx + 0.18 + rx - 0.17) / 2, ly=y + 0.018)
        box(ax, rx, y + 0.012, 0.34, 0.09, "", face=CARD, edge=col, lw=1.6)
        ax.text(rx, y + 0.03, pick, ha="center", va="center", fontsize=11.5, fontweight="bold",
                color=col if col != LAYA else "#4F6B89")
        ax.text(rx, y - 0.006, why, ha="center", va="center", fontsize=8.8, color=MUTED, linespacing=1.3)
        ny = qs[i + 1][0] + 0.06 if i + 1 < len(qs) else 0.12
        arrow(ax, qx, y - 0.06, qx, ny, "no", lx=qx - 0.025, ly=(y - 0.06 + ny) / 2, ha="right")
    box(ax, qx, 0.085, 0.34, 0.075, "", face=CARD, edge=JEV, lw=1.6)
    ax.text(qx, 0.097, "Jev", ha="center", va="center", fontsize=11.5, fontweight="bold", color=JEV)
    ax.text(qx, 0.068, "94–99% on sentiment and intents. Won typed-decisions", ha="center", va="center",
            fontsize=8.8, color=MUTED)
    brand(fig)
    save(fig, "julia-which-model-flow.png")


if __name__ == "__main__":
    hero_card_vs_full()
    round_one()
    round_two()
    emotion_gap()
    emotion_by_label()
    card_check_flow()
    which_model_flow()
