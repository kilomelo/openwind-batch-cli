"""Plot `impedance.csv` with one line per case."""

from __future__ import annotations

import argparse
import os
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

PLOT_COLUMNS = (
    "re_z",
    "im_z",
    "abs_z",
    "angle_z_rad",
    "angle_z_deg",
    "abs_y",
    "angle_y_rad",
    "angle_y_deg",
)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the impedance plotting tool."""

    parser = argparse.ArgumentParser(
        prog="owbatch-plot-impedance",
        description="Plot lines from owbatch impedance.csv, one line per case.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to an owbatch impedance.csv file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional PNG output path. If omitted, open an interactive window.",
    )
    parser.add_argument(
        "--y-column",
        choices=PLOT_COLUMNS,
        default="abs_z",
        help="Value column to plot against frequency_hz.",
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

    frame = load_impedance_frame(args.input)
    figure = plot_impedance_frame(
        frame,
        y_column=args.y_column,
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


def load_impedance_frame(path: Path) -> pd.DataFrame:
    """Read and validate an owbatch impedance export."""

    frame = pd.read_csv(path)
    required_columns = {"case_id", "frequency_hz", "note", *PLOT_COLUMNS}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    return frame


def plot_impedance_frame(
    frame: pd.DataFrame,
    *,
    y_column: str = "abs_z",
    title: str | None = None,
    note: str | None = None,
):
    """Return a matplotlib figure with one line per case."""

    if y_column not in PLOT_COLUMNS:
        raise ValueError(f"Unsupported y-column: {y_column}")

    plot_frame = frame.copy()
    if note is not None:
        plot_frame = plot_frame.loc[plot_frame["note"] == note]

    if plot_frame.empty:
        filter_label = f" for note '{note}'" if note else ""
        raise ValueError(f"No impedance rows available{filter_label}.")

    figure, axis = plt.subplots(figsize=(10, 6))

    for case_id, case_frame in plot_frame.groupby("case_id", sort=True):
        case_frame = case_frame.sort_values("frequency_hz")
        axis.plot(
            case_frame["frequency_hz"],
            case_frame[y_column],
            label=str(case_id),
            linewidth=1.5,
        )

    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel(y_column)
    axis.set_title(title or f"{y_column} by case")
    axis.grid(True, alpha=0.3)
    axis.legend(title="case_id")
    figure.tight_layout()
    return figure


if __name__ == "__main__":
    raise SystemExit(main())
