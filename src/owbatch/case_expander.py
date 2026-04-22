"""Case expansion entry points."""

from __future__ import annotations

import re
from pathlib import Path

from owbatch.config import (
    BOOL_FALSE_VALUES,
    BOOL_TRUE_VALUES,
    DERIVED_CASE_COLUMNS,
    RESERVED_CASE_COLUMNS,
)
from owbatch.csv_utils import read_csv_frame
from owbatch.models import (
    CaseDefinition,
    ExpandedCase,
    FrequencySweep,
    LoadedTemplate,
    SolverSettings,
)

BORE_OVERRIDE_RE = re.compile(r"^bore_(?P<target>[^_]+)_(?P<field>.+)$")
HOLE_OVERRIDE_RE = re.compile(r"^hole_(?P<target>[^_]+)_(?P<field>.+)$")

ALLOWED_BORE_OVERRIDE_FIELDS = {"x0", "x1", "d0", "d1", "type", "param"}
ALLOWED_HOLE_OVERRIDE_FIELDS = {
    "label",
    "position",
    "length",
    "diameter",
    "type",
    "variety",
    "reconnection",
    "group",
}


def expand_cases(template: LoadedTemplate, cases_path: Path) -> list[ExpandedCase]:
    """Expand cases.csv rows into full geometry and solver requests."""

    case_rows = _read_case_rows(cases_path)
    if not case_rows:
        raise ValueError(f"{cases_path} does not contain any cases.")

    expanded_cases: list[ExpandedCase] = []
    seen_case_ids: set[str] = set()

    for row in case_rows:
        case_id = row.get("case_id", "")
        if not case_id:
            raise ValueError(f"{cases_path} contains a case with blank 'case_id'.")
        if case_id in seen_case_ids:
            raise ValueError(f"{cases_path} contains duplicate case_id '{case_id}'.")
        seen_case_ids.add(case_id)

        definition = _build_case_definition(case_id, row)
        _validate_case_note(definition, template, cases_path)
        bore_rows = [bore_row.copy() for bore_row in template.bore_rows]
        holes_rows = [hole_row.copy() for hole_row in template.holes_rows]
        fingering_rows = [fingering_row.copy() for fingering_row in template.fingering_rows]

        _apply_transforms(definition, bore_rows, holes_rows)
        _apply_overrides(definition, bore_rows, holes_rows)

        expanded_cases.append(
            ExpandedCase(
                definition=definition,
                bore_rows=bore_rows,
                holes_rows=holes_rows,
                fingering_rows=fingering_rows,
                openwind_kwargs=_build_openwind_kwargs(definition),
            )
        )

    return expanded_cases


def _read_case_rows(cases_path: Path) -> list[dict[str, str]]:
    frame = read_csv_frame(cases_path)
    if "case_id" not in frame.columns:
        raise ValueError(f"{cases_path} is missing required column 'case_id'.")

    return frame.to_dict(orient="records")


def _build_case_definition(case_id: str, row: dict[str, str]) -> CaseDefinition:
    sweep = _parse_frequency_sweep(case_id, row)
    flute_type_instrument = _parse_optional_bool(
        case_id,
        "flute_type_instrument",
        row.get("flute_type_instrument", ""),
    )
    solver = SolverSettings(
        temperature_c=_parse_optional_float(case_id, "temperature_c", row.get("temperature_c", "")),
        losses=_parse_bool_or_string(row.get("losses", "")),
        compute_method=_empty_to_none(row.get("compute_method", "")),
        radiation_category=_empty_to_none(row.get("radiation_category", "")),
        spherical_waves=_parse_bool_or_string(row.get("spherical_waves", "")),
        player_preset=_resolve_player_preset(
            case_id,
            row.get("player_preset", ""),
            flute_type_instrument,
        ),
        source_location=_empty_to_none(row.get("source_location", "")),
    )

    geometry_overrides: dict[str, str] = {}
    transform_fields: dict[str, str] = {}

    for column_name, value in row.items():
        if column_name in RESERVED_CASE_COLUMNS or not value:
            continue
        if column_name in DERIVED_CASE_COLUMNS:
            transform_fields[column_name] = value
        else:
            geometry_overrides[column_name] = value

    return CaseDefinition(
        case_id=case_id,
        note=_empty_to_none(row.get("note", "")),
        sweep=sweep,
        solver=solver,
        geometry_overrides=geometry_overrides,
        transform_fields=transform_fields,
        raw_fields=row.copy(),
    )


def _parse_frequency_sweep(case_id: str, row: dict[str, str]) -> FrequencySweep | None:
    values = [row.get("f_start", ""), row.get("f_stop", ""), row.get("f_step", "")]
    if not any(values):
        return None
    if not all(values):
        raise ValueError(
            f"Case '{case_id}' must provide f_start, f_stop, and f_step together."
        )

    sweep = FrequencySweep(
        f_start=_parse_required_float(case_id, "f_start", row["f_start"]),
        f_stop=_parse_required_float(case_id, "f_stop", row["f_stop"]),
        f_step=_parse_required_float(case_id, "f_step", row["f_step"]),
    )
    if sweep.f_stop <= sweep.f_start:
        raise ValueError(
            f"Case '{case_id}' has invalid sweep: f_stop must be greater than f_start."
        )
    if sweep.f_step <= 0:
        raise ValueError(f"Case '{case_id}' has invalid sweep: f_step must be > 0.")
    return sweep


def _apply_transforms(
    definition: CaseDefinition,
    bore_rows: list[dict[str, str]],
    holes_rows: list[dict[str, str]],
) -> None:
    for field_name, raw_value in definition.transform_fields.items():
        if field_name == "bore_all_diameter_offset":
            offset = _parse_required_float(definition.case_id, field_name, raw_value)
            for row in bore_rows:
                row["d0"] = _format_float(_parse_required_float(definition.case_id, "d0", row["d0"]) + offset)
                row["d1"] = _format_float(_parse_required_float(definition.case_id, "d1", row["d1"]) + offset)
        elif field_name == "all_hole_diameter_scale":
            scale = _parse_required_float(definition.case_id, field_name, raw_value)
            for row in holes_rows:
                row["diameter"] = _format_float(
                    _parse_required_float(definition.case_id, "diameter", row["diameter"]) * scale
                )
        elif field_name == "upper_holes_shift":
            shift = _parse_required_float(definition.case_id, field_name, raw_value)
            matched_rows = [row for row in holes_rows if row.get("group", "").lower() == "upper"]
            if not matched_rows:
                raise ValueError(
                    f"Case '{definition.case_id}' uses upper_holes_shift but no hole rows have group=upper."
                )
            for row in matched_rows:
                row["position"] = _format_float(
                    _parse_required_float(definition.case_id, "position", row["position"]) + shift
                )


def _apply_overrides(
    definition: CaseDefinition,
    bore_rows: list[dict[str, str]],
    holes_rows: list[dict[str, str]],
) -> None:
    for field_name, raw_value in definition.geometry_overrides.items():
        bore_match = BORE_OVERRIDE_RE.match(field_name)
        if bore_match:
            target = bore_match.group("target")
            field = bore_match.group("field")
            if field not in ALLOWED_BORE_OVERRIDE_FIELDS:
                raise ValueError(
                    f"Case '{definition.case_id}' uses unsupported bore override field '{field_name}'."
                )
            row = _resolve_bore_target(definition.case_id, bore_rows, target)
            row[field] = raw_value
            continue

        hole_match = HOLE_OVERRIDE_RE.match(field_name)
        if hole_match:
            target = hole_match.group("target")
            field = hole_match.group("field")
            if field not in ALLOWED_HOLE_OVERRIDE_FIELDS:
                raise ValueError(
                    f"Case '{definition.case_id}' uses unsupported hole override field '{field_name}'."
                )
            row = _resolve_hole_target(definition.case_id, holes_rows, target)
            row[field] = raw_value
            continue

        raise ValueError(
            f"Case '{definition.case_id}' contains unsupported override column '{field_name}'."
        )


def _resolve_bore_target(
    case_id: str,
    bore_rows: list[dict[str, str]],
    target: str,
) -> dict[str, str]:
    if target.isdigit():
        index = int(target) - 1
        if 0 <= index < len(bore_rows):
            return bore_rows[index]
    for row in bore_rows:
        if row.get("segment") == target:
            return row
    raise ValueError(f"Case '{case_id}' refers to unknown bore segment '{target}'.")


def _resolve_hole_target(
    case_id: str,
    holes_rows: list[dict[str, str]],
    target: str,
) -> dict[str, str]:
    if target.isdigit():
        index = int(target) - 1
        if 0 <= index < len(holes_rows):
            return holes_rows[index]
    for row in holes_rows:
        if row.get("label") == target:
            return row
    raise ValueError(f"Case '{case_id}' refers to unknown hole '{target}'.")


def _build_openwind_kwargs(definition: CaseDefinition) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if definition.note is not None:
        kwargs["note"] = definition.note
    if definition.solver.temperature_c is not None:
        kwargs["temperature"] = definition.solver.temperature_c
    if definition.solver.losses is not None:
        kwargs["losses"] = definition.solver.losses
    if definition.solver.compute_method is not None:
        kwargs["compute_method"] = definition.solver.compute_method
    if definition.solver.radiation_category is not None:
        kwargs["radiation_category"] = definition.solver.radiation_category
    if definition.solver.spherical_waves is not None:
        kwargs["spherical_waves"] = definition.solver.spherical_waves
    if definition.solver.player_preset is not None:
        kwargs["player_preset"] = definition.solver.player_preset
    if definition.solver.source_location is not None:
        kwargs["source_location"] = definition.solver.source_location
    return kwargs


def _validate_case_note(
    definition: CaseDefinition,
    template: LoadedTemplate,
    cases_path: Path,
) -> None:
    if definition.note is None:
        return

    available_notes = [
        column_name
        for column_name in template.fingering_columns
        if column_name != "label"
    ]
    if not available_notes:
        raise ValueError(
            f"Case '{definition.case_id}' uses note '{definition.note}', "
            f"but {cases_path} points to a template without any fingering note columns."
        )
    if definition.note not in available_notes:
        raise ValueError(
            f"Case '{definition.case_id}' uses note '{definition.note}', "
            f"but available fingering notes are: {available_notes}"
        )


def _parse_optional_float(case_id: str, field_name: str, raw_value: str) -> float | None:
    if not raw_value:
        return None
    return _parse_required_float(case_id, field_name, raw_value)


def _parse_optional_bool(case_id: str, field_name: str, raw_value: str) -> bool | None:
    value = raw_value.strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in BOOL_TRUE_VALUES:
        return True
    if lowered in BOOL_FALSE_VALUES:
        return False
    raise ValueError(
        f"Case '{case_id}' has non-boolean value for '{field_name}': {raw_value!r}"
    )


def _parse_required_float(case_id: str, field_name: str, raw_value: str) -> float:
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Case '{case_id}' has non-numeric value for '{field_name}': {raw_value!r}"
        ) from exc


def _parse_bool_or_string(raw_value: str) -> bool | str | None:
    value = raw_value.strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in BOOL_TRUE_VALUES:
        return True
    if lowered in BOOL_FALSE_VALUES:
        return False
    return value


def _empty_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _resolve_player_preset(
    case_id: str,
    raw_player_preset: str,
    flute_type_instrument: bool | None,
) -> str | None:
    player_preset = _normalize_player_preset(raw_player_preset)

    if flute_type_instrument is True:
        if player_preset is None:
            return "FLUTE"
        if player_preset not in {"FLUTE", "SOPRANO_RECORDER"}:
            raise ValueError(
                f"Case '{case_id}' sets flute_type_instrument=true but player_preset="
                f"{raw_player_preset!r} is not flute-like."
            )
        return player_preset

    if flute_type_instrument is False:
        if player_preset is None:
            return "UNITARY_FLOW"
        if player_preset in {"FLUTE", "SOPRANO_RECORDER"}:
            raise ValueError(
                f"Case '{case_id}' sets flute_type_instrument=false but player_preset="
                f"{raw_player_preset!r} is flute-like."
            )
        return player_preset

    return player_preset


def _normalize_player_preset(raw_value: str) -> str | None:
    stripped = raw_value.strip()
    if not stripped:
        return None
    return stripped.upper().replace("-", "_").replace(" ", "_")


def _format_float(value: float) -> str:
    return f"{value:.12g}"
