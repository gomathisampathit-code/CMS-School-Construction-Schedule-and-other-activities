"""Gantt-style chart: one block per day of work, concrete work in green, weekday names on the date axis."""
from datetime import date, timedelta

import matplotlib.dates as md
from matplotlib.figure import Figure
from matplotlib.patches import Patch

NORMAL, CONC = "#2F80C9", "#2EAD4B"
NORMAL_EDGE, CONC_EDGE = "#1D5F9E", "#17692C"
CONC_TEXT = "#1B7A33"


def make_chart(title, rows, note=""):
    """rows: list of dicts {label, start(date), end(date), concrete(bool), suffix(str, optional)}"""
    n = len(rows)
    start = min(r["start"] for r in rows)
    end = max(r["end"] for r in rows)
    x0, x1 = md.date2num(start), md.date2num(end) + 9
    days = int(x1 - x0) + 1
    fig = Figure(figsize=(0.37 * days + 5.5, 0.42 * n + 3.2), dpi=100)
    ax = fig.subplots()

    for i, r in enumerate(rows):
        if r["concrete"]:
            ax.axhspan(i - .5, i + .5, color="#E3F6E8", zorder=0)
        elif i % 2 == 0:
            ax.axhspan(i - .5, i + .5, color="#EEF4FB", zorder=0)

    for i, r in enumerate(rows):
        s, e, c = r["start"], r["end"], r["concrete"]
        d = (e - s).days + 1
        for k in range(d):
            ax.barh(i, 0.86, left=md.date2num(s) + k - 0.43, height=.7 if c else .55,
                    color=CONC if c else NORMAL, edgecolor=CONC_EDGE if c else NORMAL_EDGE,
                    lw=1.2 if c else .6, zorder=3)
        lab = f"{s:%a %d %b}" if d == 1 else f"{s:%a %d %b} – {e:%a %d %b}"
        ax.text(md.date2num(e) + 0.75, i, f"{lab}  ({d} day{'s' if d > 1 else ''}){r.get('suffix', '')}",
                va="center", fontsize=11.5 if c else 10.5, fontweight="bold" if c else "normal",
                color=CONC_TEXT if c else "#222", zorder=5)

    ax.set_yticks(range(n))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=12)
    for tl, r in zip(ax.get_yticklabels(), rows):
        if r["concrete"]:
            tl.set_fontweight("bold")
            tl.set_color(CONC_TEXT)
    ax.invert_yaxis()
    ax.set_xlim(x0 - .5, x1)
    ax.set_ylim(n - .5, -1.3)

    ticks = [x0 + k for k in range(days)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{(start + timedelta(k)).day}\n{(start + timedelta(k)):%a}" for k in range(days)], fontsize=9.5)
    ax.set_xticks([t - .5 for t in ticks] + [ticks[-1] + .5], minor=True)
    ax.grid(axis="x", which="minor", color="#D9D9D9", lw=.7)
    ax.tick_params(axis="x", which="minor", length=0)
    ax.set_axisbelow(True)

    m = date(start.year, start.month, 1)
    while md.date2num(m) < x1:
        nx = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        if md.date2num(m) > x0:
            ax.axvline(md.date2num(m) - .5, color="#666", lw=1.4, ls="--", zorder=2)
        a, b = max(md.date2num(m) - .5, x0 - .5), min(md.date2num(nx) - .5, x1)
        if b - a > 8:
            ax.text((a + b) / 2, -.95, f"{m:%B %Y}".upper(), ha="center", fontsize=13,
                    fontweight="bold", color="#12355B")
        m = nx

    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.legend(handles=[Patch(color=CONC, label="Concrete work"), Patch(color=NORMAL, label="Other work")],
              loc="lower left", fontsize=11.5, frameon=True)
    ax.set_xlabel("Date (one tick = one day; each block = one day of work)", fontsize=12)
    fig.suptitle(title, fontsize=20, fontweight="bold", y=.985)
    ax.set_title(note, fontsize=12, color="#444", pad=26)
    fig.tight_layout(rect=(0, 0, 1, .955))
    return fig
