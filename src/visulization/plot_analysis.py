"""Plot per-case harmonic deviation summaries from owbatch analysis.csv."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path
from typing import Sequence


def _ensure_matplotlib_cache_dirs() -> None:
    """Point matplotlib/fontconfig caches at writable temp locations."""

    if "MPLCONFIGDIR" not in os.environ:
        mpl_config_dir = Path(tempfile.gettempdir()) / "owbatch-mpl-config"
        mpl_config_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(mpl_config_dir)

    if "XDG_CACHE_HOME" not in os.environ:
        xdg_cache_dir = Path(tempfile.gettempdir()) / "owbatch-xdg-cache"
        xdg_cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ["XDG_CACHE_HOME"] = str(xdg_cache_dir)


_ensure_matplotlib_cache_dirs()

import matplotlib.pyplot as plt
import pandas as pd

DELTA_COLUMN_PATTERN = re.compile(r"^delta(\d+)_cents$")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the analysis plotting tool."""

    parser = argparse.ArgumentParser(
        prog="owbatch-plot-analysis",
        description=(
            "Plot per-case harmonic deviation lines from owbatch analysis.csv. "
            "The tool auto-detects populated deltaN_cents columns."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to an owbatch analysis.csv file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional PNG output path. If omitted, open an interactive window.",
    )
    parser.add_argument(
        "--title",
        help="Optional figure title.",
    )
    parser.add_argument(
        "--note",
        help="Optional note filter. Only rows with this note are plotted.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    analysis_frame = load_analysis_frame(args.input)
    figure = plot_analysis_frame(
        analysis_frame,
        title=args.title,
        note=args.note,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.output, dpi=150)
        plt.close(figure)
    else:
        plt.show()

    return 0


def load_analysis_frame(path: Path) -> pd.DataFrame:
    """Read and minimally validate an owbatch analysis export."""

    frame = pd.read_csv(path)
    required_columns = {"case_id"}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    if "note" not in frame.columns:
        frame["note"] = ""
    return frame


def plot_analysis_frame(
    frame: pd.DataFrame,
    *,
    title: str | None = None,
    note: str | None = None,
):
    """Return a matplotlib figure for deltaN_cents lines across cases."""

    plot_frame, delta_columns = prepare_analysis_plot_frame(frame, note=note)
    x_positions = list(range(len(plot_frame)))
    case_labels = build_case_labels(plot_frame)

    figure, axis = plt.subplots(figsize=(10, 5.5))
    for column in delta_columns:
        axis.plot(
            x_positions,
            plot_frame[column],
            marker="o",
            linewidth=1.6,
            label=column,
        )

    axis.set_xticks(x_positions)
    axis.set_xticklabels(case_labels, rotation=30, ha="right")
    axis.set_xlabel("Case")
    axis.set_ylabel("Deviation [cents]")
    axis.set_title(title or _build_default_title(note))
    axis.grid(True, alpha=0.3)
    axis.legend(title="Series")
    figure.tight_layout()
    return figure


def prepare_analysis_plot_frame(
    frame: pd.DataFrame,
    *,
    note: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Filter and validate an analysis frame for plotting."""

    plot_frame = frame.copy()
    if note is not None:
        plot_frame = plot_frame.loc[plot_frame["note"] == note]

    if plot_frame.empty:
        filter_label = f" for note '{note}'" if note else ""
        raise ValueError(f"No analysis rows available{filter_label}.")

    delta_columns = detect_populated_delta_columns(plot_frame)
    if not delta_columns:
        raise ValueError(
            "No populated deltaN_cents columns were found in the analysis data."
        )

    plot_frame = plot_frame.reset_index(drop=True)
    return plot_frame, delta_columns


def detect_populated_delta_columns(frame: pd.DataFrame) -> list[str]:
    """Return sorted deltaN_cents columns that contain at least one value."""

    indexed_columns: list[tuple[int, str]] = []
    for column in frame.columns:
        match = DELTA_COLUMN_PATTERN.match(str(column))
        if not match:
            continue
        if frame[column].notna().any():
            indexed_columns.append((int(match.group(1)), str(column)))
    indexed_columns.sort()
    return [column for _, column in indexed_columns]


def build_case_labels(frame: pd.DataFrame) -> list[str]:
    """Build readable x-axis labels, disambiguating duplicate case ids with note."""

    case_ids = frame["case_id"].astype(str)
    duplicate_case_ids = set(case_ids[case_ids.duplicated(keep=False)])
    labels: list[str] = []
    for row in frame.to_dict(orient="records"):
        case_id = str(row["case_id"])
        note = str(row.get("note", "") or "")
        if case_id in duplicate_case_ids and note:
            labels.append(f"{case_id}:{note}")
        else:
            labels.append(case_id)
    return labels


def _build_default_title(note: str | None) -> str:
    if note:
        return f"Harmonic Deviation by case: {note}"
    return "Harmonic Deviation by case"


if __name__ == "__main__":
    raise SystemExit(main())
