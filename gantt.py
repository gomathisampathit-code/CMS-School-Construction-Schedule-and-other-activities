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
LATE_RED = "#C0392B"


def _overlaps(r, w0, w1):
    s, e = r["p_start"], r["p_end"]
    if r.get("a_start"):
        s = min(s, r["a_start"])
        e = max(e, r.get("a_end") or r["a_start"])
    return s <= w1 and e >= w0


def make_combined_chart(title, rows, note="", today=None, start=None, end=None):
    """Planned (light, top lane) and actual (solid, lower lane) in ONE chart, one block per day.
    rows: dicts {label, p_start, p_end, a_start, a_end, concrete}. start/end = window of dates to show.
    Returns None when nothing falls inside the window."""
    today = today or date.today()
    lo = min(r["p_start"] for r in rows) if rows else today
    hi = max(max(r["p_end"], r.get("a_end") or r.get("a_start") or r["p_end"]) for r in rows) if rows else today
    start = start or lo
    end = end or hi
    rows = [r for r in rows if _overlaps(r, start, end)]
    if not rows:
        return None
    n = len(rows)
    days = (end - start).days + 1
    x0, x1 = md.date2num(start), md.date2num(end)

    # layout in inches: [labels | chart | date table]
    day_w = 0.36 if days <= 31 else (0.28 if days <= 50 else 0.2)
    left_in, plot_in, table_in = 3.2, max(days * day_w, 5.0), 5.1
    top_in, bottom_in, row_in = 1.55, 1.05, 0.62
    W = left_in + plot_in + table_in + 0.2
    H = top_in + bottom_in + n * row_in
    fig = Figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([left_in / W, bottom_in / H, plot_in / W, n * row_in / H])
    off = 0.2

    for i, r in enumerate(rows):
        if r["concrete"]:
            ax.axhspan(i - .5, i + .5, color="#E3F6E8", zorder=0)
        elif i % 2 == 0:
            ax.axhspan(i - .5, i + .5, color="#EEF4FB", zorder=0)

    def blocks(s, e, y, face, edge):
        for k in range((e - s).days + 1):
            d = s + timedelta(days=k)
            if start <= d <= end:
                ax.barh(y, 0.86, left=md.date2num(d) - 0.43, height=0.34, color=face, edgecolor=edge, lw=.9, zorder=3)

    tr = ax.get_yaxis_transform()          # x in axes fraction, y in data units -> text table to the right of the plot
    ax.text(1.02, -0.78, "PLANNED", transform=tr, fontsize=11.5, fontweight="bold", color="#555", va="center")
    ax.text(1.02 + 0.5 * table_in / plot_in, -0.78, "ACTUAL", transform=tr, fontsize=11.5, fontweight="bold",
            color="#12355B", va="center")
    for i, r in enumerate(rows):
        c = r["concrete"]
        ps, pe = r["p_start"], r["p_end"]
        pdays = (pe - ps).days + 1
        blocks(ps, pe, i - off, PLAN_CONC if c else PLAN_NORMAL, PLAN_CONC_EDGE if c else PLAN_NORMAL_EDGE)
        ax.text(1.02, i, f"{ps:%d %b} – {pe:%d %b}\n{pdays} day{'s' if pdays > 1 else ''}", transform=tr,
                fontsize=11, color="#555", va="center", linespacing=1.15)
        xa = 1.02 + 0.5 * table_in / plot_in
        if r.get("a_start"):
            a_s = r["a_start"]
            a_e = max(r.get("a_end") or max(today, a_s), a_s)
            blocks(a_s, a_e, i + off, CONC if c else NORMAL, CONC_EDGE if c else NORMAL_EDGE)
            ad = (a_e - a_s).days + 1
            late = a_s > ps or (r.get("a_end") and r["a_end"] > pe) or (not r.get("a_end") and today > pe)
            end_txt = f"{a_e:%d %b}" if r.get("a_end") else "now"
            tail = f"{ad} day{'s' if ad > 1 else ''}" + ("" if r.get("a_end") else " · running") + (" · LATE" if late else "")
            col = LATE_RED if late else (CONC_TEXT if c else "#12355B")
            ax.text(xa, i, f"{a_s:%d %b} – {end_txt}\n{tail}", transform=tr, fontsize=11, fontweight="bold",
                    color=col, va="center", linespacing=1.15)
        else:
            ax.text(xa, i, "not started", transform=tr, fontsize=10.5, color="#999", va="center", style="italic")

    ax.set_yticks(range(n))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=13)
    for tl, r in zip(ax.get_yticklabels(), rows):
        if r["concrete"]:
            tl.set_fontweight("bold")
            tl.set_color(CONC_TEXT)
    ax.invert_yaxis()
    ax.set_xlim(x0 - .5, x1 + .5)
    ax.set_ylim(n - .5, -1.2)

    ticks = [x0 + k for k in range(days)]
    labs = []
    for k in range(days):
        d = start + timedelta(k)
        labs.append(f"{d.day}\n{d:%a}\n{d:%b}" if (k == 0 or d.day == 1) else f"{d.day}\n{d:%a}")
    ax.set_xticks(ticks)
    ax.set_xticklabels(labs, fontsize=10.5 if day_w >= 0.28 else 8.5)
    ax.set_xticks([t - .5 for t in ticks] + [ticks[-1] + .5], minor=True)
    ax.grid(axis="x", which="minor", color="#D0D0D0", lw=.8)
    ax.tick_params(axis="x", which="minor", length=0)
    ax.set_axisbelow(True)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(axis="y", length=0)

    m = date(start.year, start.month, 1)
    while md.date2num(m) <= x1:
        nx = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        if md.date2num(m) > x0:
            ax.axvline(md.date2num(m) - .5, color="#666", lw=1.5, ls="--", zorder=2)
        a, b = max(md.date2num(m) - .5, x0 - .5), min(md.date2num(nx) - .5, x1 + .5)
        if b - a > 5:
            ax.text((a + b) / 2, -.78, f"{m:%B %Y}".upper(), ha="center", va="center", fontsize=13, fontweight="bold",
                    color="#12355B")
        m = nx
    if start <= today <= end:
        ax.axvline(md.date2num(today), color="#D62728", lw=2, ls=":", zorder=4)
        ax.text(md.date2num(today), -0.3, " Today ", color="#D62728", ha="center", va="center", fontsize=10.5,
                fontweight="bold", zorder=6, bbox=dict(facecolor="white", edgecolor="#D62728", boxstyle="round,pad=0.2"))

    fig.text(left_in / W - 0.0, 1 - 0.40 / H, title, fontsize=19, fontweight="bold", ha="left", va="center")
    fig.text(left_in / W, 1 - 0.78 / H, note, fontsize=11.5, color="#444", ha="left", va="center")
    handles = [Patch(facecolor=PLAN_NORMAL, edgecolor=PLAN_NORMAL_EDGE, label="Planned"),
               Patch(facecolor=NORMAL, edgecolor=NORMAL_EDGE, label="Actual"),
               Patch(facecolor=PLAN_CONC, edgecolor=PLAN_CONC_EDGE, label="Planned concrete"),
               Patch(facecolor=CONC, edgecolor=CONC_EDGE, label="Actual concrete"),
               Patch(facecolor="white", edgecolor=LATE_RED, label="Red text = late")]
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(left_in / W, 1 - 1.12 / H), ncol=5,
               fontsize=10.5, frameon=False, columnspacing=1.6, handlelength=1.4)
    return fig
