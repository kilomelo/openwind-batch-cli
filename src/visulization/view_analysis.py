"""Interactive analysis viewer powered by mplcursors hover tooltips."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence

import pandas as pd

from owbatch.analysis import nearest_harmonic_multiple
from visulization.plot_analysis import (
    _ensure_matplotlib_cache_dirs,
    build_case_labels,
    load_analysis_frame,
    prepare_analysis_plot_frame,
)

_ensure_matplotlib_cache_dirs()

import matplotlib.pyplot as plt
import mplcursors

DELTA_COLUMN_PATTERN = re.compile(r"^delta(\d+)_cents$")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the interactive analysis viewer."""

    parser = argparse.ArgumentParser(
        prog="owbatch-view-analysis",
        description=(
            "Open an interactive matplotlib window for owbatch analysis.csv. "
            "Hover over a plotted point to inspect its exact case/frequency/deviation values."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to an owbatch analysis.csv file.",
    )
    parser.add_argument(
        "--title",
        help="Optional figure title.",
    )
    parser.add_argument(
        "--note",
        help="Optional note filter. Only rows with this note are shown.",
    )
    parser.add_argument(
        "--hover-radius",
        type=float,
        default=8.0,
        help="Point hover tolerance in screen pixels.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    analysis_frame = load_analysis_frame(args.input)
    plot_interactive_analysis_frame(
        analysis_frame,
        title=args.title,
        note=args.note,
        hover_radius=args.hover_radius,
    )
    plt.show()
    return 0


def plot_interactive_analysis_frame(
    frame: pd.DataFrame,
    *,
    title: str | None = None,
    note: str | None = None,
    hover_radius: float = 8.0,
):
    """Return a figure and mplcursors cursor for interactive analysis browsing."""

    plot_frame, delta_columns = prepare_analysis_plot_frame(frame, note=note)
    x_positions = list(range(len(plot_frame)))
    case_labels = build_case_labels(plot_frame)

    figure, axis = plt.subplots(figsize=(11, 6))
    line_to_column: dict[object, str] = {}
    for column in delta_columns:
        line = axis.plot(
            x_positions,
            plot_frame[column],
            marker="o",
            linewidth=1.6,
            label=column,
        )[0]
        line.set_pickradius(hover_radius)
        line_to_column[line] = column

    axis.set_xticks(x_positions)
    axis.set_xticklabels(case_labels, rotation=30, ha="right")
    axis.set_xlabel("Case")
    axis.set_ylabel("Deviation [cents]")
    axis.set_title(title or _build_default_title(note))
    axis.grid(True, alpha=0.3)
    axis.legend(title="Series")

    cursor = bind_analysis_cursor(plot_frame, line_to_column)
    figure.tight_layout()
    return figure, cursor


def bind_analysis_cursor(
    plot_frame: pd.DataFrame,
    line_to_column: dict[object, str],
):
    """Attach an mplcursors hover cursor to the plotted analysis lines."""

    cursor = mplcursors.cursor(
        list(line_to_column),
        hover=mplcursors.HoverMode.Transient,
    )

    @cursor.connect("add")
    def _on_add(selection) -> None:
        column = line_to_column[selection.artist]
        point_index = resolve_selection_point_index(selection)
        row = plot_frame.iloc[point_index]
        selection.annotation.set_text(format_analysis_point_label(row, column))
        bbox_patch = selection.annotation.get_bbox_patch()
        if bbox_patch is not None:
            bbox_patch.set(boxstyle="round", fc="white", ec="0.6", alpha=0.95)
        if selection.annotation.arrow_patch is not None:
            selection.annotation.arrow_patch.set(arrowstyle="->", color="0.4")

    return cursor


def resolve_selection_point_index(selection) -> int:
    """Map an mplcursors selection back to the nearest actual plotted data point."""

    line = selection.artist
    target_x, target_y = selection.target
    x_data = line.get_xdata(orig=False)
    y_data = line.get_ydata(orig=False)
    return min(
        range(len(x_data)),
        key=lambda index: (float(x_data[index]) - float(target_x)) ** 2
        + (float(y_data[index]) - float(target_y)) ** 2,
    )


def format_analysis_point_label(row: pd.Series | dict[str, object], column: str) -> str:
    """Return a hover label for one deltaN_cents point."""

    series = dict(row) if not isinstance(row, dict) else row
    match = DELTA_COLUMN_PATTERN.match(column)
    peak_index = int(match.group(1)) if match else None

    case_id = str(series.get("case_id", ""))
    note = str(series.get("note", "") or "")
    lines = [f"case: {case_id}"]
    if note:
        lines.append(f"note: {note}")
    lines.append(f"{column}: {float(series[column]):.6f} cents")

    if peak_index is not None:
        frequency_key = f"f{peak_index}"
        ratio_key = f"h{peak_index}"
        frequency_hz = series.get(frequency_key)
        harmonic_ratio = series.get(ratio_key)
        if pd.notna(frequency_hz):
            lines.append(f"{frequency_key}: {float(frequency_hz):.6f} Hz")
        if pd.notna(harmonic_ratio):
            harmonic_ratio = float(harmonic_ratio)
            lines.append(f"{ratio_key}: {harmonic_ratio:.6f} x f1")
            lines.append(
                "nearest multiple: "
                f"{nearest_harmonic_multiple(harmonic_ratio, 1.0)} x f1"
            )
    return "\n".join(lines)


def _build_default_title(note: str | None) -> str:
    if note:
        return f"Interactive Harmonic Deviation: {note}"
    return "Interactive Harmonic Deviation by case"


if __name__ == "__main__":
    raise SystemExit(main())
