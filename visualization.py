"""
visualization.py — Stage 4: Data Visualization
Consumes results from analysis.py and renders matplotlib charts.
Imported by study_tracker.py; has no UI of its own.
"""

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

import analysis as analysis


# ── Style config ──────────────────────────────────────────────────────────────

PALETTE = ["#4C9BE8", "#6BCB77", "#FFD93D", "#FF6B6B", "#C77DFF",
           "#F4A261", "#48CAE4", "#E76F51", "#74C69D", "#ADB5BD"]

def _apply_style():
    plt.rcParams.update({
        "figure.facecolor" : "#1a1a2e",
        "axes.facecolor"   : "#16213e",
        "axes.edgecolor"   : "#444466",
        "axes.labelcolor"  : "#ccccdd",
        "axes.titlecolor"  : "#ffffff",
        "axes.grid"        : True,
        "grid.color"       : "#2a2a4a",
        "grid.linewidth"   : 0.5,
        "xtick.color"      : "#aaaacc",
        "ytick.color"      : "#aaaacc",
        "text.color"       : "#ccccdd",
        "font.family"      : "monospace",
        "legend.facecolor" : "#1a1a2e",
        "legend.edgecolor" : "#444466",
    })


# ── Chart 1: Study hours per subject (horizontal bar) ────────────────────────

def chart_hours_per_subject(ax, since=None):
    result = analysis.hours_per_subject(since)
    if result is None or result.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#aaaacc")
        ax.set_title("Hours per Subject")
        return

    subjects = result.index.tolist()
    hours    = result.values.tolist()
    colors   = [PALETTE[i % len(PALETTE)] for i in range(len(subjects))]

    bars = ax.barh(subjects, hours, color=colors, height=0.6, zorder=3)

    for bar, val in zip(bars, hours):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}h", va="center", fontsize=8, color="#ffffff")

    ax.set_xlabel("Hours")
    ax.set_title("Hours per Subject", pad=12, fontsize=11, fontweight="bold")
    ax.invert_yaxis()


# ── Chart 2: Weekly study totals (line + area) ───────────────────────────────

def chart_weekly_totals(ax, since=None):
    result = analysis.weekly_totals(since)
    if result is None or result.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#aaaacc")
        ax.set_title("Weekly Totals")
        return

    weeks  = [w.strftime("%b %d") for w in result.index]
    totals = result.values

    ax.plot(weeks, totals, color=PALETTE[0], linewidth=2, marker="o",
            markersize=5, zorder=3)
    ax.fill_between(weeks, totals, alpha=0.25, color=PALETTE[0], zorder=2)

    ax.set_ylabel("Hours")
    ax.set_title("Weekly Study Totals", pad=12, fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", rotation=30)


# ── Chart 3: Study trend — 7-day rolling average ─────────────────────────────

def chart_study_trend(ax, since=None):
    df = analysis.load_combined(since)
    if df.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#aaaacc")
        ax.set_title("Study Trend")
        return

    df = df.dropna(subset=["date"])
    daily = (
        df.set_index("date")["hours"]
          .resample("D")
          .sum()
    )

    rolling = daily.rolling(window=7, min_periods=1).mean()
    labels  = [d.strftime("%b %d") for d in daily.index]

    ax.bar(labels, daily.values, color=PALETTE[2], alpha=0.4,
           label="Daily", zorder=2)
    ax.plot(labels, rolling.values, color=PALETTE[3], linewidth=2,
            label="7-day avg", zorder=3)

    ax.set_ylabel("Hours")
    ax.set_title("Study Trend (7-day avg)", pad=12, fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=8)

    n = max(1, len(labels) // 8)
    for i, label in enumerate(ax.get_xticklabels()):
        if i % n != 0:
            label.set_visible(False)


# ── Chart 4: GitHub-style activity heatmap ───────────────────────────────────

def chart_heatmap(ax, since=None):
    df = analysis.load_combined(since)
    if df.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#aaaacc")
        ax.set_title("Activity Heatmap")
        return

    df = df.dropna(subset=["date"])
    daily = (
        df.set_index("date")["hours"]
          .resample("D")
          .sum()
    )

    all_dates = pd.date_range(start=daily.index.min(), end=daily.index.max(), freq="D")
    daily     = daily.reindex(all_dates, fill_value=0)

    start_dow = daily.index[0].dayofweek
    pad       = start_dow
    values    = np.concatenate([np.zeros(pad), daily.values])

    total_cells = int(np.ceil(len(values) / 7)) * 7
    values      = np.pad(values, (0, total_cells - len(values)), constant_values=np.nan)
    grid        = values.reshape(-1, 7).T

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "study_heat", ["#16213e", "#0f3460", "#4C9BE8", "#6BCB77"]
    )

    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0,
                   vmax=max(daily.max(), 1), interpolation="nearest")

    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                       fontsize=7)
    ax.set_xticks([])
    ax.set_title("Activity Heatmap", pad=12, fontsize=11, fontweight="bold")

    plt.colorbar(im, ax=ax, label="Hours", pad=0.02,
                 fraction=0.03, orientation="vertical")


# ── Chart 5: Peak study hours (hour-of-day bar chart) ────────────────────────

def chart_peak_hours(ax, since=None):
    result = analysis.peak_study_hours(since)
    if result is None or result.sum() == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#aaaacc")
        ax.set_title("Peak Study Hours")
        return

    hours  = result.index.tolist()
    totals = result.values.tolist()
    colors = [PALETTE[0] if t == max(totals) else PALETTE[4] for t in totals]

    ax.bar(hours, totals, color=colors, width=0.7, zorder=3)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Hours studied")
    ax.set_title("Peak Study Hours", pad=12, fontsize=11, fontweight="bold")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)],
                       rotation=45, fontsize=7)


# ── Dashboard: all charts in one window ──────────────────────────────────────

def show_dashboard(since=None, label="All time"):
    """
    Build and return the dashboard figure.
    - CLI: call plt.show(fig) after this
    - Streamlit: pass the returned fig to st.pyplot(fig)
    """
    _apply_style()

    fig = plt.figure(figsize=(16, 10), facecolor="#1a1a2e")
    fig.suptitle(f"Study Tracker — Dashboard  [{label}]",
                 fontsize=15, fontweight="bold", color="#ffffff", y=0.98)

    gs = gridspec.GridSpec(
        2, 3,
        figure=fig,
        hspace=0.45,
        wspace=0.38,
        left=0.06, right=0.97,
        top=0.92,  bottom=0.10,
    )

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])

    chart_hours_per_subject(ax1, since)
    chart_weekly_totals(ax2, since)
    chart_study_trend(ax3, since)
    chart_heatmap(ax4, since)
    chart_peak_hours(ax5, since)

    fig.add_subplot(gs[1, 2]).set_visible(False)

    return fig