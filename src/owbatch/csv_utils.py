"""Helpers for robust CSV loading."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError


def read_csv_frame(path: Path) -> pd.DataFrame:
    """Read a CSV file while tolerating trailing empty cells.

    The current workflow often involves hand-edited CSV files. A common mistake
    is leaving a few extra commas at the end of a row. Pandas interprets those
    rows in a surprising way and silently shifts values into the wrong columns.
    This loader trims only trailing empty surplus cells and raises a clear error
    for any real column-count mismatch.
    """

    try:
        with path.open(newline="", encoding="utf-8") as handle:
            raw_rows = list(csv.reader(handle))
    except csv.Error as exc:
        raise ValueError(f"{path} is not a valid CSV file: {exc}") from exc

    if not raw_rows:
        raise ValueError(f"{path} is empty.")

    header = [str(cell).strip() for cell in raw_rows[0]]
    if not any(header):
        raise ValueError(f"{path} has an empty header row.")

    expected_columns = len(header)
    normalized_rows: list[list[str]] = []
    for line_number, row in enumerate(raw_rows[1:], start=2):
        cleaned_row = [str(cell).strip() for cell in row]

        if len(cleaned_row) > expected_columns:
            extras = cleaned_row[expected_columns:]
            if any(cell for cell in extras):
                raise ValueError(
                    f"{path} line {line_number} has {len(cleaned_row)} fields, "
                    f"but the header has {expected_columns}. "
                    f"Unexpected extra values: {extras!r}"
                )
            cleaned_row = cleaned_row[:expected_columns]

        if len(cleaned_row) < expected_columns:
            cleaned_row.extend([""] * (expected_columns - len(cleaned_row)))

        normalized_rows.append(cleaned_row)

    try:
        frame = pd.DataFrame(normalized_rows, columns=header, dtype=str)
    except EmptyDataError as exc:
        raise ValueError(f"{path} is empty.") from exc

    frame = frame.rename(columns=lambda value: str(value).strip())
    if frame.columns.duplicated().any():
        duplicated = frame.columns[frame.columns.duplicated()].tolist()
        raise ValueError(f"{path} has duplicated columns: {duplicated}")

    frame = frame.apply(lambda column: column.map(_clean_string))
    if not frame.empty:
        frame = frame.loc[~frame.apply(_is_blank_row, axis=1)]

    return frame


def _clean_string(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _is_blank_row(row: pd.Series) -> bool:
    return all(not str(value).strip() for value in row.tolist())
