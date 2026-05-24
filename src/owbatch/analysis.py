"""Per-case analysis summaries built on top of extracted peak features."""

from __future__ import annotations

import math

import pandas as pd

from owbatch.config import DEFAULT_PRIMARY_PEAK_COUNT, build_analysis_columns

A4_FREQUENCY_HZ = 440.0
A4_MIDI_NOTE = 69
PITCH_CLASS_NAMES = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)


def extract_analysis_rows(
    features_frame: pd.DataFrame,
    *,
    peak_count: int = DEFAULT_PRIMARY_PEAK_COUNT,
    case_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Summarize the first ``peak_count`` extracted peaks into one row per case."""

    if peak_count <= 0:
        raise ValueError(f"peak_count must be > 0, got {peak_count}.")

    columns = build_analysis_columns(peak_count)
    if features_frame.empty and (case_frame is None or case_frame.empty):
        return pd.DataFrame(columns=columns)

    required_columns = {
        "case_id",
        "note",
        "kind",
        "index",
        "frequency_hz",
        "q_factor",
        "amplitude",
    }
    feature_groups: dict[tuple[str, str], pd.DataFrame] = {}
    if not features_frame.empty:
        missing_columns = required_columns.difference(features_frame.columns)
        if missing_columns:
            missing_display = ", ".join(sorted(missing_columns))
            raise ValueError(
                "features_frame is missing required columns for analysis: "
                f"{missing_display}"
            )
        feature_groups = {
            (str(case_id), str(note)): grouped_frame.sort_values(["index", "frequency_hz"]).reset_index(drop=True)
            for (case_id, note), grouped_frame in features_frame.groupby(
                ["case_id", "note"],
                sort=False,
                dropna=False,
            )
        }

    analysis_rows: list[dict[str, object]] = []
    if case_frame is not None and not case_frame.empty:
        _validate_case_frame(case_frame)
        seen_groups: set[tuple[str, str]] = set()
        unique_case_frame = case_frame.drop_duplicates(["case_id", "note"])
        for case_row in unique_case_frame.to_dict(orient="records"):
            group_key = (str(case_row["case_id"]), str(case_row.get("note", "")))
            seen_groups.add(group_key)
            analysis_rows.append(
                _build_analysis_row_from_group(
                    group_key,
                    feature_groups.get(group_key),
                    peak_count=peak_count,
                    default_feature_family=str(case_row.get("primary_feature_family", "") or ""),
                )
            )
        missing_feature_groups = sorted(set(feature_groups).difference(seen_groups))
        for group_key in missing_feature_groups:
            analysis_rows.append(
                _build_analysis_row_from_group(
                    group_key,
                    feature_groups[group_key],
                    peak_count=peak_count,
                    default_feature_family="",
                )
            )
    else:
        for group_key, grouped_frame in feature_groups.items():
            analysis_rows.append(
                _build_analysis_row_from_group(
                    group_key,
                    grouped_frame,
                    peak_count=peak_count,
                    default_feature_family="",
                )
            )

    return pd.DataFrame(analysis_rows, columns=columns)


def nearest_equal_temperament_pitch(frequency_hz: float) -> tuple[str, float]:
    """Return the nearest 12-TET pitch name and its cents deviation from ``frequency_hz``."""

    if frequency_hz <= 0:
        raise ValueError(f"frequency_hz must be > 0, got {frequency_hz}.")

    midi_note = int(round(A4_MIDI_NOTE + 12.0 * math.log2(frequency_hz / A4_FREQUENCY_HZ)))
    reference_hz = A4_FREQUENCY_HZ * (2.0 ** ((midi_note - A4_MIDI_NOTE) / 12.0))
    cents = cents_from_reference(frequency_hz, reference_hz)
    pitch_class = PITCH_CLASS_NAMES[midi_note % 12]
    octave = (midi_note // 12) - 1
    return f"{pitch_class}{octave}", cents


def cents_from_reference(frequency_hz: float, reference_hz: float) -> float:
    """Return the cents deviation from ``reference_hz`` to ``frequency_hz``."""

    if frequency_hz <= 0 or reference_hz <= 0:
        raise ValueError(
            "frequency_hz and reference_hz must both be > 0, "
            f"got {frequency_hz} and {reference_hz}."
        )
    return 1200.0 * math.log2(frequency_hz / reference_hz)


def nearest_harmonic_multiple(
    frequency_hz: float,
    base_frequency_hz: float,
) -> int:
    """Return the nearest integer multiple of ``base_frequency_hz`` for ``frequency_hz``."""

    if frequency_hz <= 0 or base_frequency_hz <= 0:
        raise ValueError(
            "frequency_hz and base_frequency_hz must both be > 0, "
            f"got {frequency_hz} and {base_frequency_hz}."
        )

    ratio = frequency_hz / base_frequency_hz
    # Use floor(x + 0.5) instead of round(x) so .5 ties do not use banker's rounding.
    return max(1, int(math.floor(ratio + 0.5)))


def _build_analysis_row_from_group(
    group_key: tuple[str, str],
    case_frame: pd.DataFrame | None,
    *,
    peak_count: int,
    default_feature_family: str,
) -> dict[str, object]:
    case_id, note = group_key
    analysis_row: dict[str, object] = {
        "case_id": case_id,
        "note": note,
        "feature_family": default_feature_family,
    }
    if case_frame is None or case_frame.empty:
        return analysis_row

    feature_families = {
        str(value)
        for value in case_frame["kind"].dropna().astype(str).tolist()
        if str(value)
    }
    if len(feature_families) > 1:
        raise ValueError(
            "Each case/note analysis group must resolve to a single feature family, "
            f"got {sorted(feature_families)} for case_id={case_id!r}."
        )

    analysis_row["feature_family"] = next(iter(feature_families), default_feature_family)

    indexed_rows = {
        int(feature_row["index"]): feature_row
        for feature_row in case_frame.head(peak_count).to_dict(orient="records")
    }

    base_frequency = _read_frequency(indexed_rows.get(1))
    for peak_index in range(1, peak_count + 1):
        feature_row = indexed_rows.get(peak_index)
        if feature_row is None:
            continue

        frequency_hz = float(feature_row["frequency_hz"])
        pitch_name, pitch_cents = nearest_equal_temperament_pitch(frequency_hz)

        analysis_row[f"f{peak_index}"] = frequency_hz
        analysis_row[f"pitch{peak_index}"] = pitch_name
        analysis_row[f"pitch{peak_index}_cents"] = float(pitch_cents)
        analysis_row[f"q{peak_index}"] = float(feature_row["q_factor"])
        analysis_row[f"a{peak_index}"] = float(feature_row["amplitude"])

        if peak_index >= 2 and base_frequency is not None:
            harmonic_ratio = frequency_hz / base_frequency
            harmonic_multiple = nearest_harmonic_multiple(frequency_hz, base_frequency)
            analysis_row[f"h{peak_index}"] = harmonic_ratio
            analysis_row[f"delta{peak_index}_cents"] = cents_from_reference(
                frequency_hz,
                base_frequency * harmonic_multiple,
            )

    return analysis_row


def _read_frequency(feature_row: dict[str, object] | None) -> float | None:
    if feature_row is None:
        return None
    frequency_hz = float(feature_row["frequency_hz"])
    if frequency_hz <= 0:
        return None
    return frequency_hz


def _validate_case_frame(case_frame: pd.DataFrame) -> None:
    required_columns = {"case_id", "note"}
    missing_columns = required_columns.difference(case_frame.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(
            "case_frame is missing required columns for analysis: "
            f"{missing_display}"
        )
