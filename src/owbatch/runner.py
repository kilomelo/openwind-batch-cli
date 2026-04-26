"""Top-level pipeline orchestration."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from owbatch.case_expander import expand_cases
from owbatch.config import (
    ANALYSIS_COLUMNS,
    FEATURE_COLUMNS,
    GEOMETRY_UNIT,
    build_output_paths,
)
from owbatch.models import ExpandedCase, InspectRequest, RunRequest
from owbatch.response import build_response_rows, compute_admittance
from owbatch.template_loader import load_template
from owbatch.writers import (
    sanitize_case_filename,
    write_impedance_csv,
    write_impedance_list_csv,
    write_placeholder_csv,
)


def inspect_inputs(request: InspectRequest) -> str:
    """Return expanded template/case data for `owbatch inspect`."""

    template = load_template(request.template_dir)
    expanded_cases = expand_cases(template, request.cases_path)

    payload = {
        "template_dir": str(request.template_dir),
        "cases_path": str(request.cases_path),
        "template": {
            "manifest": {
                "bore_path": str(template.manifest.bore_path),
                "holes_path": str(template.manifest.holes_path),
                "fingering_path": str(template.manifest.fingering_path),
            },
            "bore_columns": template.bore_columns,
            "holes_columns": template.holes_columns,
            "fingering_columns": template.fingering_columns,
            "bore_rows": template.bore_rows,
            "holes_rows": template.holes_rows,
            "fingering_rows": template.fingering_rows,
        },
        "expanded_cases": [asdict(case) for case in expanded_cases],
    }
    return json.dumps(payload, indent=2)


def run_batch(request: RunRequest) -> str:
    """Execute the current batch and write CSV outputs."""

    template = load_template(request.template_dir)
    expanded_cases = expand_cases(template, request.cases_path)
    output_paths = build_output_paths(request.out_dir)
    request.out_dir.mkdir(parents=True, exist_ok=True)

    impedance_rows: list[dict[str, float | str]] = []
    for case in expanded_cases:
        frequencies, impedance = _compute_case_impedance(case)
        admittance = _compute_admittance(impedance)
        impedance_rows.extend(
            build_response_rows(
                case_id=case.definition.case_id,
                note=case.definition.note or "",
                frequencies=frequencies,
                impedance=impedance,
            )
        )
        write_impedance_list_csv(
            _build_impedance_list_path(
                output_paths["impedance_lists_dir"],
                case.definition.case_id,
            ),
            case_id=case.definition.case_id,
            note=case.definition.note,
            frequencies=frequencies.tolist(),
            admittance_magnitude=np.abs(admittance).tolist(),
            admittance_phase_rad=np.angle(admittance).tolist(),
        )

    write_impedance_csv(output_paths["impedance"], impedance_rows)
    write_placeholder_csv(output_paths["features"], FEATURE_COLUMNS)
    write_placeholder_csv(output_paths["analysis"], ANALYSIS_COLUMNS)

    return "\n".join(
        [
            f"cases_processed: {len(expanded_cases)}",
            f"impedance_rows: {len(impedance_rows)}",
            f"impedance_csv: {output_paths['impedance']}",
            f"impedance_lists_dir: {output_paths['impedance_lists_dir']}",
            f"features_csv: {output_paths['features']}",
            f"analysis_csv: {output_paths['analysis']}",
            "status: aggregate impedance and per-case impedance lists are complete; features and analysis are placeholder headers for now.",
        ]
    )


def _compute_case_impedance(case: ExpandedCase) -> tuple[np.ndarray, np.ndarray]:
    if case.definition.sweep is None:
        raise ValueError(f"Case '{case.definition.case_id}' is missing frequency sweep data.")

    frequencies = _build_frequency_axis(
        case.definition.sweep.f_start,
        case.definition.sweep.f_stop,
        case.definition.sweep.f_step,
    )
    impedance_computation = _load_impedance_computation()
    result = impedance_computation(
        frequencies,
        _build_openwind_bore(case.bore_rows),
        _build_openwind_holes(case.holes_rows),
        _build_openwind_fingering(case.fingering_rows),
        unit=GEOMETRY_UNIT,
        diameter=True,
        nondim=False,
        **_materialize_openwind_kwargs(case.openwind_kwargs),
    )
    return (
        np.asarray(result.frequencies, dtype=float),
        np.asarray(result.impedance, dtype=complex),
    )


def _build_frequency_axis(f_start: float, f_stop: float, f_step: float) -> np.ndarray:
    return np.arange(f_start, f_stop + (0.5 * f_step), f_step, dtype=float)


def _build_openwind_bore(bore_rows: list[dict[str, str]]) -> list[list[str]]:
    table: list[list[str]] = []
    for row in bore_rows:
        values = [row["x0"], row["x1"], row["d0"], row["d1"], row["type"]]
        if row.get("param", ""):
            values.append(row["param"])
        table.append(values)
    return table


def _build_openwind_holes(holes_rows: list[dict[str, str]]) -> list[list[str]]:
    if not holes_rows:
        return []

    headers = ["label", "position", "length", "diameter", "type"]
    optional_headers = ["variety", "reconnection"]
    headers.extend(
        header
        for header in optional_headers
        if any(row.get(header, "") for row in holes_rows)
    )

    table = [headers]
    for row in holes_rows:
        row_values = [
            row["label"],
            row["position"],
            row["length"],
            row["diameter"],
            row.get("type", "") or "linear",
        ]
        for header in headers[5:]:
            if header == "variety":
                row_values.append(row.get(header, "") or "hole")
            else:
                row_values.append(row.get(header, ""))
        table.append(row_values)
    return table


def _build_openwind_fingering(
    fingering_rows: list[dict[str, str]],
) -> list[list[str]]:
    if not fingering_rows:
        return []
    headers = list(fingering_rows[0].keys())
    table = [headers]
    for row in fingering_rows:
        table.append([row.get(header, "") for header in headers])
    return table


def _compute_admittance(impedance: np.ndarray) -> np.ndarray:
    return compute_admittance(impedance)


def _build_impedance_list_path(output_dir: Path, case_id: str) -> Path:
    return output_dir / f"{sanitize_case_filename(case_id)}.csv"


def _load_impedance_computation():
    _prepare_runtime_environment()
    from openwind import ImpedanceComputation

    return ImpedanceComputation


def _load_player():
    _prepare_runtime_environment()
    from openwind import Player

    return Player


def _materialize_openwind_kwargs(openwind_kwargs: dict[str, object]) -> dict[str, object]:
    kwargs = dict(openwind_kwargs)
    player_preset = kwargs.pop("player_preset", None)
    if player_preset is not None:
        try:
            kwargs["player"] = _load_player()(str(player_preset))
        except Exception as exc:
            raise ValueError(
                f"OpenWind rejected player_preset {player_preset!r}. "
                "Check the preset name and player-related case settings."
            ) from exc
    return kwargs


def _prepare_runtime_environment() -> None:
    cache_root = Path(tempfile.gettempdir()) / "owbatch-runtime-cache"
    mpl_cache = cache_root / "mpl"
    xdg_cache = cache_root / "xdg"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    xdg_cache.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))
