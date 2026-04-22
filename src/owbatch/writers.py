"""CSV writing entry points."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from owbatch.config import IMPEDANCE_COLUMNS


def write_impedance_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    """Write impedance rows to CSV."""

    frame = pd.DataFrame(rows, columns=IMPEDANCE_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_placeholder_csv(path: Path, columns: tuple[str, ...]) -> None:
    """Write an empty CSV with headers only."""

    frame = pd.DataFrame(columns=columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_impedance_list_csv(
    path: Path,
    case_id: str,
    note: str | None,
    frequencies: list[float],
    admittance_magnitude: list[float],
    admittance_phase_rad: list[float],
) -> None:
    """Write one OpenWind-style impedance list file for a single case."""

    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = [f"case_id:{case_id}"]
    if note:
        metadata.append(f"note:{note}")

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"#{'; '.join(metadata)}\n")
        handle.write("#f[Hz] abs(Y) angle(Y)[rad]\n")
        for frequency_hz, y_abs, y_angle in zip(
            frequencies,
            admittance_magnitude,
            admittance_phase_rad,
        ):
            handle.write(
                f"{_format_frequency(frequency_hz)} "
                f"{_format_scientific(y_abs)} "
                f"{_format_scientific(y_angle)}\n"
            )


def sanitize_case_filename(case_id: str) -> str:
    """Return a filesystem-safe filename stem for one case id."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", case_id.strip()).strip("._")
    return cleaned or "case"


def _format_frequency(value: float) -> str:
    return f"{float(value):.12g}"


def _format_scientific(value: float) -> str:
    formatted = f"{float(value):.8e}"
    return re.sub(r"e([+-])0*(\d+)$", r"e\1\2", formatted)
