"""Plot impedance/admittance responses with OpenWind-aligned semantics."""

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

from owbatch.response import (
    build_response_frame,
    format_angle_values,
    get_angle_axis_label,
    get_mode_columns,
    get_modulus_axis_label,
    resolve_requested_response_mode,
)

PLOT_MODES = ("auto", "impedance", "admittance")
ANGLE_UNITS = ("rad", "deg", "pi")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the response plotting tool."""

    parser = argparse.ArgumentParser(
        prog="owbatch-plot-impedance",
        description=(
            "Plot owbatch frequency responses with OpenWind-style semantics: "
            "auto follows case metadata; impedance draws |Z|/angle(Z); "
            "admittance draws |Y|/angle(Y)."
        ),
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
        "--mode",
        choices=PLOT_MODES,
        default="auto",
        help="Response mode to display. 'auto' follows case metadata.",
    )
    parser.add_argument(
        "--angle-unit",
        choices=ANGLE_UNITS,
        default="rad",
        help="Display unit for the angle subplot.",
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

    response_frame = load_impedance_frame(args.input)
    figure = plot_response_frame(
        response_frame,
        mode=args.mode,
        angle_unit=args.angle_unit,
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
    """Read and minimally validate an owbatch impedance export."""

    frame = pd.read_csv(path)
    required_columns = {"case_id", "frequency_hz", "re_z", "im_z"}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    if "note" not in frame.columns:
        frame["note"] = ""
    return frame


def plot_response_frame(
    frame: pd.DataFrame,
    *,
    mode: str = "auto",
    angle_unit: str = "rad",
    title: str | None = None,
    note: str | None = None,
):
    """Return a 2-panel matplotlib figure for one response mode."""

    if mode not in PLOT_MODES:
        raise ValueError(f"Unsupported response mode: {mode}")
    if angle_unit not in ANGLE_UNITS:
        raise ValueError(f"Unsupported angle unit: {angle_unit}")

    plot_frame = build_response_frame(frame)
    if note is not None:
        plot_frame = plot_frame.loc[plot_frame["note"] == note]

    if plot_frame.empty:
        filter_label = f" for note '{note}'" if note else ""
        raise ValueError(f"No impedance rows available{filter_label}.")

    resolved_mode = resolve_requested_response_mode(plot_frame, requested_mode=mode)
    modulus_column, angle_column = get_mode_columns(resolved_mode)
    figure, (modulus_axis, angle_axis) = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=(10, 8),
        height_ratios=(2.0, 1.2),
    )

    for case_id, case_frame in plot_frame.groupby("case_id", sort=False):
        case_frame = case_frame.sort_values("frequency_hz")
        line = modulus_axis.plot(
            case_frame["frequency_hz"],
            case_frame[modulus_column],
            label=str(case_id),
            linewidth=1.5,
        )[0]
        angle_axis.plot(
            case_frame["frequency_hz"],
            format_angle_values(case_frame[angle_column], unit=angle_unit),
            color=line.get_color(),
            linewidth=1.2,
        )

    modulus_axis.set_ylabel(get_modulus_axis_label(resolved_mode))
    modulus_axis.set_title(title or _build_default_title(resolved_mode, note))
    modulus_axis.grid(True, alpha=0.3)
    modulus_axis.legend(title="case_id")

    angle_axis.set_xlabel("Frequency (Hz)")
    angle_axis.set_ylabel(get_angle_axis_label(resolved_mode, unit=angle_unit))
    angle_axis.grid(True, alpha=0.3)

    figure.tight_layout()
    return figure


def _build_default_title(mode: str, note: str | None) -> str:
    mode_label = "Impedance" if mode == "impedance" else "Admittance"
    if note:
        return f"{mode_label} Response: {note}"
    return f"{mode_label} Response by case"


if __name__ == "__main__":
    raise SystemExit(main())
