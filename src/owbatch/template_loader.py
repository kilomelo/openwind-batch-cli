"""Template loading entry points."""

from __future__ import annotations

from pathlib import Path

from owbatch.csv_utils import read_csv_frame
from owbatch.config import (
    BORE_TEMPLATE_FILENAME,
    BORE_TEMPLATE_REQUIRED_COLUMNS,
    FINGERING_TEMPLATE_FILENAME,
    FINGERING_TEMPLATE_REQUIRED_COLUMNS,
    HOLES_TEMPLATE_FILENAME,
    HOLES_TEMPLATE_REQUIRED_COLUMNS,
)
from owbatch.models import LoadedTemplate, TemplateManifest


def build_template_manifest(template_dir: Path) -> TemplateManifest:
    """Return the expected CSV paths for one template directory."""

    return TemplateManifest(
        template_dir=template_dir,
        bore_path=template_dir / BORE_TEMPLATE_FILENAME,
        holes_path=template_dir / HOLES_TEMPLATE_FILENAME,
        fingering_path=template_dir / FINGERING_TEMPLATE_FILENAME,
    )


def load_template(template_dir: Path) -> LoadedTemplate:
    """Load template CSV files into memory."""

    manifest = build_template_manifest(template_dir)
    _ensure_template_files_exist(manifest)

    bore_columns, bore_rows = _read_csv_rows(manifest.bore_path)
    holes_columns, holes_rows = _read_csv_rows(manifest.holes_path)
    fingering_columns, fingering_rows = _read_csv_rows(manifest.fingering_path)

    _validate_required_columns(
        manifest.bore_path,
        bore_columns,
        BORE_TEMPLATE_REQUIRED_COLUMNS,
    )
    _validate_required_columns(
        manifest.holes_path,
        holes_columns,
        HOLES_TEMPLATE_REQUIRED_COLUMNS,
    )
    _validate_required_columns(
        manifest.fingering_path,
        fingering_columns,
        FINGERING_TEMPLATE_REQUIRED_COLUMNS,
    )

    if not bore_rows:
        raise ValueError(f"{manifest.bore_path} must contain at least one bore row.")

    if "segment" not in bore_columns:
        bore_columns = ["segment", *bore_columns]
        for index, row in enumerate(bore_rows, start=1):
            row["segment"] = str(index)
    else:
        for index, row in enumerate(bore_rows, start=1):
            row["segment"] = row["segment"] or str(index)

    _validate_unique_values(manifest.bore_path, bore_rows, "segment")
    _validate_unique_values(manifest.holes_path, holes_rows, "label")
    _validate_unique_values(manifest.fingering_path, fingering_rows, "label")

    return LoadedTemplate(
        manifest=manifest,
        bore_columns=bore_columns,
        holes_columns=holes_columns,
        fingering_columns=fingering_columns,
        bore_rows=bore_rows,
        holes_rows=holes_rows,
        fingering_rows=fingering_rows,
    )


def _ensure_template_files_exist(manifest: TemplateManifest) -> None:
    missing_paths = [
        path
        for path in (manifest.bore_path, manifest.holes_path, manifest.fingering_path)
        if not path.exists()
    ]
    if missing_paths:
        formatted = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Missing template file(s): {formatted}")


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    frame = read_csv_frame(path)
    return frame.columns.tolist(), frame.to_dict(orient="records")


def _validate_required_columns(
    path: Path,
    columns: list[str],
    required_columns: tuple[str, ...],
) -> None:
    missing = [column for column in required_columns if column not in columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def _validate_unique_values(
    path: Path,
    rows: list[dict[str, str]],
    column_name: str,
) -> None:
    seen: set[str] = set()
    for row in rows:
        value = row.get(column_name, "")
        if not value:
            raise ValueError(f"{path} has a blank value in '{column_name}'.")
        if value in seen:
            raise ValueError(f"{path} has duplicate '{column_name}' value: {value}")
        seen.add(value)
