"""Feature extraction built on top of the shared response semantics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from owbatch.config import DEFAULT_PRIMARY_PEAK_COUNT
from owbatch.response import build_case_response_metadata_from_row, build_response_frame

DEFAULT_PEAK_COUNT = DEFAULT_PRIMARY_PEAK_COUNT


def extract_frequency_features(
    frame: pd.DataFrame,
    *,
    peak_count: int = DEFAULT_PEAK_COUNT,
) -> pd.DataFrame:
    """Extract the first ``peak_count`` semantic peaks for each case/note group.

    The peak family is selected from the response metadata:
    - non flute-like cases default to ``z_resonance``
    - flute-like cases default to ``y_resonance``

    Frequencies and Q-factors are obtained from OpenWind's phase-based peak
    utilities so the extracted semantics stay aligned with the solver.
    """

    if peak_count <= 0:
        raise ValueError(f"peak_count must be > 0, got {peak_count}.")

    response_frame = build_response_frame(frame)
    if response_frame.empty:
        return pd.DataFrame()

    feature_rows: list[dict[str, object]] = []
    group_columns = ["case_id", "note"]
    for (_, _), case_frame in response_frame.groupby(group_columns, sort=True, dropna=False):
        case_frame = case_frame.sort_values("frequency_hz").reset_index(drop=True)
        feature_rows.extend(_extract_case_feature_rows(case_frame, peak_count=peak_count))

    return pd.DataFrame(feature_rows)


def _extract_case_feature_rows(
    case_frame: pd.DataFrame,
    *,
    peak_count: int,
) -> list[dict[str, object]]:
    if len(case_frame) < 3:
        return []

    metadata = build_case_response_metadata_from_row(case_frame.iloc[0].to_dict())
    kind = str(case_frame.iloc[0].get("primary_feature_family") or metadata["primary_feature_family"])

    frequencies = case_frame["frequency_hz"].to_numpy(dtype=float)
    impedance = _build_complex_values(case_frame["re_z"], case_frame["im_z"])
    signal = _select_feature_signal(case_frame, kind)

    peak_frequencies, q_factors, _ = _find_feature_peaks(
        frequencies,
        signal,
        kind=kind,
        peak_count=peak_count,
    )

    if len(peak_frequencies) == 0:
        return []

    impedance_at_peaks = _interpolate_complex_values(frequencies, impedance, peak_frequencies)
    admittance_at_peaks = _interpolate_complex_values(
        frequencies,
        _build_complex_values_from_response(case_frame, prefix="y"),
        peak_frequencies,
    )

    feature_rows: list[dict[str, object]] = []
    for index, (frequency_hz, q_factor, z_value, y_value) in enumerate(
        zip(peak_frequencies, q_factors, impedance_at_peaks, admittance_at_peaks),
        start=1,
    ):
        amplitude = abs(z_value) if kind.startswith("z_") else abs(y_value)
        feature_rows.append(
            {
                "case_id": str(case_frame.iloc[0]["case_id"]),
                "note": str(case_frame.iloc[0].get("note", "")),
                "kind": kind,
                "index": index,
                "frequency_hz": float(frequency_hz),
                "q_factor": float(q_factor),
                "amplitude": float(amplitude),
                "abs_z": float(abs(z_value)),
                "angle_z_deg": float(np.degrees(np.angle(z_value))),
                "abs_y": float(abs(y_value)),
                "angle_y_deg": float(np.degrees(np.angle(y_value))),
            }
        )
    return feature_rows


def _find_feature_peaks(
    frequencies: np.ndarray,
    signal: np.ndarray,
    *,
    kind: str,
    peak_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    peak_finder = _load_peak_finder(kind)
    peak_frequencies, q_factors, values = peak_finder(
        frequencies,
        signal,
        k=peak_count,
        display_warning=False,
    )
    return (
        np.asarray(peak_frequencies, dtype=float),
        np.asarray(q_factors, dtype=float),
        np.asarray(values, dtype=complex),
    )


def _load_peak_finder(kind: str):
    from openwind.impedance_tools import (
        antiresonance_peaks_from_phase,
        resonance_peaks_from_phase,
    )

    peak_finders = {
        "z_resonance": resonance_peaks_from_phase,
        "z_antiresonance": antiresonance_peaks_from_phase,
        "y_resonance": resonance_peaks_from_phase,
        "y_antiresonance": antiresonance_peaks_from_phase,
    }
    try:
        return peak_finders[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported feature family: {kind}") from exc


def _select_feature_signal(case_frame: pd.DataFrame, kind: str) -> np.ndarray:
    if kind.startswith("z_"):
        return _build_complex_values(case_frame["re_z"], case_frame["im_z"])
    if kind.startswith("y_"):
        return _build_complex_values_from_response(case_frame, prefix="y")
    raise ValueError(f"Unsupported feature family: {kind}")


def _build_complex_values(
    real_values: Sequence[float] | pd.Series,
    imag_values: Sequence[float] | pd.Series,
) -> np.ndarray:
    return np.asarray(real_values, dtype=float) + 1j * np.asarray(imag_values, dtype=float)


def _build_complex_values_from_response(case_frame: pd.DataFrame, *, prefix: str) -> np.ndarray:
    magnitude = case_frame[f"abs_{prefix}"].to_numpy(dtype=float)
    angle = case_frame[f"angle_{prefix}_rad"].to_numpy(dtype=float)
    return magnitude * np.exp(1j * angle)


def _interpolate_complex_values(
    sample_frequencies: np.ndarray,
    values: np.ndarray,
    target_frequencies: np.ndarray,
) -> np.ndarray:
    real_part = np.interp(target_frequencies, sample_frequencies, np.real(values))
    imag_part = np.interp(target_frequencies, sample_frequencies, np.imag(values))
    return real_part + 1j * imag_part
