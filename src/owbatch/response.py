"""Shared response semantics derived from complex input impedance.

This module is the semantic bridge between raw impedance samples and all
higher-level consumers such as plotting, feature extraction, and analysis.
The current project phase follows OpenWind demo semantics with a simplified
reference impedance ``Zc0 = 1``:

- impedance mode:
  - modulus = ``|Z|``
  - angle = ``angle(Z)``
- admittance mode:
  - modulus = ``|Y| = |1 / Z|``
  - angle = ``angle(Y) = angle(1 / Z)``

Keeping this logic in one place prevents plotting and future feature
extractors from silently diverging.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import numpy as np
import pandas as pd

ResponseMode = Literal["impedance", "admittance"]
RequestedResponseMode = Literal["auto", "impedance", "admittance"]
AngleUnit = Literal["rad", "deg", "pi"]

FLUTE_LIKE_PLAYER_PRESETS = frozenset({"FLUTE", "SOPRANO_RECORDER"})
DEFAULT_PLAYER_PRESET = "UNITARY_FLOW"
RESPONSE_METADATA_COLUMNS = (
    "player_preset",
    "is_flute_like",
    "default_response_mode",
    "primary_feature_family",
)


def build_response_frame(
    frame: pd.DataFrame,
    *,
    zc0: complex | float = 1.0,
) -> pd.DataFrame:
    """Return a copy of ``frame`` enriched with derived response quantities."""

    required_columns = {"frequency_hz", "re_z", "im_z"}
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(
            f"Response derivation requires columns {sorted(required_columns)}; "
            f"missing {missing_columns}."
        )

    response_frame = annotate_response_metadata(frame)
    impedance = (
        response_frame["re_z"].to_numpy(dtype=float)
        + 1j * response_frame["im_z"].to_numpy(dtype=float)
    )
    admittance = compute_admittance(impedance, zc0=zc0)

    response_frame["abs_z"] = np.abs(impedance)
    response_frame["angle_z_rad"] = np.angle(impedance)
    response_frame["angle_z_deg"] = np.degrees(response_frame["angle_z_rad"])
    response_frame["abs_y"] = np.abs(admittance)
    response_frame["angle_y_rad"] = np.angle(admittance)
    response_frame["angle_y_deg"] = np.degrees(response_frame["angle_y_rad"])
    return response_frame


def build_response_rows(
    *,
    case_id: str,
    note: str,
    frequencies: np.ndarray,
    impedance: np.ndarray,
    player_preset: str | None = None,
    zc0: complex | float = 1.0,
) -> list[dict[str, float | str]]:
    """Return CSV-ready response rows for one case."""

    frame = pd.DataFrame(
        {
            "case_id": case_id,
            "note": note,
            "frequency_hz": np.asarray(frequencies, dtype=float),
            "re_z": np.real(impedance),
            "im_z": np.imag(impedance),
        }
    )
    frame["player_preset"] = player_preset
    return build_response_frame(frame, zc0=zc0).to_dict(orient="records")


def compute_admittance(
    impedance: np.ndarray,
    *,
    zc0: complex | float = 1.0,
) -> np.ndarray:
    """Return ``Y = Zc0 / Z`` with ``NaN`` where the division is undefined."""

    impedance = np.asarray(impedance, dtype=complex)
    admittance = np.full_like(impedance, np.nan + 1j * np.nan, dtype=complex)
    nonzero_mask = np.abs(impedance) > 0
    admittance[nonzero_mask] = zc0 / impedance[nonzero_mask]
    return admittance


def get_mode_columns(mode: ResponseMode) -> tuple[str, str]:
    """Return the modulus column and angle-in-radians column for one mode."""

    if mode == "impedance":
        return "abs_z", "angle_z_rad"
    if mode == "admittance":
        return "abs_y", "angle_y_rad"
    raise ValueError(f"Unsupported response mode: {mode}")


def annotate_response_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``frame`` enriched with reusable response metadata."""

    response_frame = frame.copy()
    if "player_preset" not in response_frame.columns:
        response_frame["player_preset"] = None

    metadata = [
        build_case_response_metadata(player_preset=value)
        for value in response_frame["player_preset"].tolist()
    ]
    metadata_frame = pd.DataFrame(metadata, index=response_frame.index)

    for column_name in RESPONSE_METADATA_COLUMNS:
        response_frame[column_name] = metadata_frame[column_name]

    return response_frame


def format_angle_values(values: pd.Series, *, unit: AngleUnit) -> np.ndarray:
    """Return angle values converted to the requested display unit."""

    angle_values = values.to_numpy(dtype=float)
    if unit == "rad":
        return angle_values
    if unit == "deg":
        return np.degrees(angle_values)
    if unit == "pi":
        return angle_values / np.pi
    raise ValueError(f"Unsupported angle unit: {unit}")


def get_angle_axis_label(mode: ResponseMode, *, unit: AngleUnit) -> str:
    """Return the semantic y-axis label for the angle subplot."""

    symbol = "Z" if mode == "impedance" else "Y"
    if unit == "rad":
        return f"angle({symbol}) [rad]"
    if unit == "deg":
        return f"angle({symbol}) [deg]"
    if unit == "pi":
        return f"angle({symbol}) / pi"
    raise ValueError(f"Unsupported angle unit: {unit}")


def get_modulus_axis_label(mode: ResponseMode) -> str:
    """Return the semantic y-axis label for the modulus subplot."""

    return "|Z|" if mode == "impedance" else "|Y|"


def build_case_response_metadata(
    *,
    player_preset: str | None,
) -> dict[str, object]:
    """Return semantic metadata derived from one case's player preset."""

    normalized_player_preset = normalize_player_preset(player_preset)
    default_response_mode = infer_default_response_mode(normalized_player_preset)
    return {
        "player_preset": normalized_player_preset,
        "is_flute_like": is_flute_like_player_preset(normalized_player_preset),
        "default_response_mode": default_response_mode,
        "primary_feature_family": infer_primary_feature_family(normalized_player_preset),
    }


def build_case_response_metadata_from_row(
    row: Mapping[str, object],
) -> dict[str, object]:
    """Return semantic metadata for one case/group row-like object."""

    return build_case_response_metadata(player_preset=row.get("player_preset"))


def resolve_requested_response_mode(
    frame: pd.DataFrame,
    *,
    requested_mode: RequestedResponseMode = "auto",
) -> ResponseMode:
    """Resolve ``auto`` into a concrete response mode for one plotted dataset."""

    if requested_mode in {"impedance", "admittance"}:
        return requested_mode
    if requested_mode != "auto":
        raise ValueError(f"Unsupported requested response mode: {requested_mode}")

    annotated_frame = annotate_response_metadata(frame)
    available_modes = sorted(
        {
            str(mode)
            for mode in annotated_frame["default_response_mode"].dropna().unique().tolist()
        }
    )
    if not available_modes:
        return infer_default_response_mode(None)
    if len(available_modes) == 1:
        return available_modes[0]  # type: ignore[return-value]
    raise ValueError(
        "Auto response mode is ambiguous because the selected cases map to "
        f"multiple semantic defaults: {available_modes}. "
        "Specify --mode impedance or --mode admittance explicitly."
    )


def infer_default_response_mode(player_preset: str | None) -> ResponseMode:
    """Infer the most natural response family to inspect for one player preset.

    This does not change the raw computation. It only captures the current
    semantic policy for later consumers such as plots and feature selection.
    """

    if is_flute_like_player_preset(player_preset):
        return "admittance"
    return "impedance"


def infer_primary_feature_family(player_preset: str | None) -> str:
    """Infer the future default feature family for one player preset."""

    if is_flute_like_player_preset(player_preset):
        return "y_resonance"
    return "z_resonance"


def is_flute_like_player_preset(player_preset: str | None) -> bool:
    """Return whether one player preset should be interpreted as flute-like."""

    return normalize_player_preset(player_preset) in FLUTE_LIKE_PLAYER_PRESETS


def normalize_player_preset(player_preset: object) -> str:
    """Normalize one preset name for semantic use and CSV export."""

    if player_preset is None:
        return DEFAULT_PLAYER_PRESET
    if pd.isna(player_preset):
        return DEFAULT_PLAYER_PRESET
    normalized = str(player_preset).strip().upper()
    return normalized or DEFAULT_PLAYER_PRESET
