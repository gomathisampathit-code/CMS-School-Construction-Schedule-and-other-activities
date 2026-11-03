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


# ---------------------------------------------------------------- planned + actual in ONE chart
PLAN_NORMAL, PLAN_CONC = "#BBD3EE", "#B5E3C1"
PLAN_NORMAL_EDGE, PLAN_CONC_EDGE = "#7FA6D3", "#7CC48F"


def make_combined_chart(title, rows, note="", today=None):
    """rows: dicts {label, p_start, p_end, a_start, a_end, concrete}.
    Each activity has two lanes: planned (light, top) and actual (solid, below). One block per day."""
    today = today or date.today()
    n = len(rows)
    ends, starts = [], []
    for r in rows:
        starts.append(r["p_start"])
        ends.append(r["p_end"])
        if r.get("a_start"):
            a_end = r.get("a_end") or max(today, r["a_start"])
            starts.append(r["a_start"])
            ends.append(max(a_end, r["a_start"]))
    start, end = min(starts), max(ends)
    x0, x1 = md.date2num(start), md.date2num(end) + 12
    days = int(x1 - x0) + 1
    fig = Figure(figsize=(0.37 * days + 5.5, 0.62 * n + 3.4), dpi=100)
    ax = fig.subplots()
    off = 0.2

    for i, r in enumerate(rows):
        if r["concrete"]:
            ax.axhspan(i - .5, i + .5, color="#E3F6E8", zorder=0)
        elif i % 2 == 0:
            ax.axhspan(i - .5, i + .5, color="#EEF4FB", zorder=0)

    def lane(i, s, e, y, face, edge, text, bold=False, color="#222"):
        d = (e - s).days + 1
        for k in range(d):
            ax.barh(y, 0.86, left=md.date2num(s) + k - 0.43, height=0.32, color=face, edgecolor=edge, lw=.8, zorder=3)
        ax.text(md.date2num(e) + 0.75, y, text, va="center", fontsize=9.5, fontweight="bold" if bold else "normal",
                color=color, zorder=5)

    for i, r in enumerate(rows):
        c = r["concrete"]
        ps, pe = r["p_start"], r["p_end"]
        pd_ = (pe - ps).days + 1
        plan_txt = (f"Plan: {ps:%a %d %b}" if pd_ == 1 else f"Plan: {ps:%a %d %b} – {pe:%a %d %b}") + f" ({pd_}d)"
        lane(i, ps, pe, i - off, PLAN_CONC if c else PLAN_NORMAL, PLAN_CONC_EDGE if c else PLAN_NORMAL_EDGE,
             plan_txt, color="#666")
        if r.get("a_start"):
            a_s = r["a_start"]
            a_e = r.get("a_end") or max(today, a_s)
            a_e = max(a_e, a_s)
            ad = (a_e - a_s).days + 1
            txt = (f"Actual: {a_s:%a %d %b}" if ad == 1 else f"Actual: {a_s:%a %d %b} – {a_e:%a %d %b}") + f" ({ad}d)"
            if not r.get("a_end"):
                txt += " – in progress"
            lane(i, a_s, a_e, i + off, CONC if c else NORMAL, CONC_EDGE if c else NORMAL_EDGE, txt,
                 bold=True, color=CONC_TEXT if c else "#12355B")

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
    if start <= today <= end + timedelta(days=12):
        ax.axvline(md.date2num(today), color="#D62728", lw=1.6, ls=":", zorder=4)
        ax.text(md.date2num(today), -0.62, " Today ", color="#D62728", ha="center", va="center", fontsize=10, fontweight="bold",
                zorder=6, bbox=dict(facecolor="white", edgecolor="#D62728", boxstyle="round,pad=0.2"))

    m = date(start.year, start.month, 1)
    while md.date2num(m) < x1:
        nx = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        if md.date2num(m) > x0:
            ax.axvline(md.date2num(m) - .5, color="#666", lw=1.4, ls="--", zorder=2)
        a, b = max(md.date2num(m) - .5, x0 - .5), min(md.date2num(nx) - .5, x1)
        if b - a > 8:
            ax.text((a + b) / 2, -.95, f"{m:%B %Y}".upper(), ha="center", fontsize=13, fontweight="bold", color="#12355B")
        m = nx

    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.legend(handles=[Patch(facecolor=PLAN_NORMAL, edgecolor=PLAN_NORMAL_EDGE, label="Planned (top lane)"),
                       Patch(facecolor=NORMAL, edgecolor=NORMAL_EDGE, label="Actual (lower lane)"),
                       Patch(facecolor=CONC, edgecolor=CONC_EDGE, label="Concrete work – actual"),
                       Patch(facecolor=PLAN_CONC, edgecolor=PLAN_CONC_EDGE, label="Concrete work – planned")],
              loc="lower left", fontsize=10.5, frameon=True)
    ax.set_xlabel("Date (one tick = one day; each block = one day of work)", fontsize=12)
    fig.suptitle(title, fontsize=20, fontweight="bold", y=.985)
    ax.set_title(note, fontsize=12, color="#444", pad=26)
    fig.tight_layout(rect=(0, 0, 1, .955))
    return fig
