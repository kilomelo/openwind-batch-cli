from __future__ import annotations

import math

import pandas as pd
import pytest

from owbatch.analysis import (
    cents_from_reference,
    extract_analysis_rows,
    nearest_equal_temperament_pitch,
    nearest_harmonic_multiple,
)
from owbatch.config import ANALYSIS_COLUMNS


def test_nearest_equal_temperament_pitch_returns_name_and_cents() -> None:
    pitch_name, cents = nearest_equal_temperament_pitch(440.0)

    assert pitch_name == "A4"
    assert cents == pytest.approx(0.0)


def test_extract_analysis_rows_builds_harmonic_summary() -> None:
    features_frame = pd.DataFrame(
        [
            {
                "case_id": "demo",
                "note": "open",
                "kind": "y_resonance",
                "index": 1,
                "frequency_hz": 440.0,
                "q_factor": 50.0,
                "amplitude": 1.2,
            },
            {
                "case_id": "demo",
                "note": "open",
                "kind": "y_resonance",
                "index": 2,
                "frequency_hz": 880.0,
                "q_factor": 60.0,
                "amplitude": 0.9,
            },
            {
                "case_id": "demo",
                "note": "open",
                "kind": "y_resonance",
                "index": 3,
                "frequency_hz": 1320.0,
                "q_factor": 70.0,
                "amplitude": 0.7,
            },
        ]
    )

    analysis_frame = extract_analysis_rows(features_frame)

    assert tuple(analysis_frame.columns) == ANALYSIS_COLUMNS
    assert len(analysis_frame) == 1

    row = analysis_frame.iloc[0]
    assert row["case_id"] == "demo"
    assert row["note"] == "open"
    assert row["feature_family"] == "y_resonance"
    assert row["f1"] == pytest.approx(440.0)
    assert row["f2"] == pytest.approx(880.0)
    assert row["f3"] == pytest.approx(1320.0)
    assert row["pitch1"] == "A4"
    assert row["pitch1_cents"] == pytest.approx(0.0)
    assert row["pitch2"] == "A5"
    assert row["pitch2_cents"] == pytest.approx(0.0)
    assert row["pitch3"] == "E6"
    assert row["h2"] == pytest.approx(2.0)
    assert row["h3"] == pytest.approx(3.0)
    assert row["delta2_cents"] == pytest.approx(0.0)
    assert row["delta3_cents"] == pytest.approx(0.0)
    assert row["q1"] == pytest.approx(50.0)
    assert row["q2"] == pytest.approx(60.0)
    assert row["q3"] == pytest.approx(70.0)
    assert row["a1"] == pytest.approx(1.2)
    assert row["a2"] == pytest.approx(0.9)
    assert row["a3"] == pytest.approx(0.7)


def test_extract_analysis_rows_uses_nearest_harmonic_multiple_for_delta_cents() -> None:
    features_frame = pd.DataFrame(
        [
            {
                "case_id": "flow_probe",
                "note": "all_closed",
                "kind": "z_resonance",
                "index": 1,
                "frequency_hz": 132.48449920052258,
                "q_factor": 41.306606490875545,
                "amplitude": 140193192.63632798,
            },
            {
                "case_id": "flow_probe",
                "note": "all_closed",
                "kind": "z_resonance",
                "index": 2,
                "frequency_hz": 392.3913282035871,
                "q_factor": 116.68325986799127,
                "amplitude": 108849409.02004363,
            },
            {
                "case_id": "flow_probe",
                "note": "all_closed",
                "kind": "z_resonance",
                "index": 3,
                "frequency_hz": 652.4447545425186,
                "q_factor": 191.55943556815228,
                "amplitude": 21207118.712195836,
            },
        ]
    )

    analysis_frame = extract_analysis_rows(features_frame)
    row = analysis_frame.iloc[0]

    assert row["h2"] == pytest.approx(2.961790477916071)
    assert row["h3"] == pytest.approx(4.924687480268975)
    assert nearest_harmonic_multiple(row["f2"], row["f1"]) == 3
    assert nearest_harmonic_multiple(row["f3"], row["f1"]) == 5
    assert row["delta2_cents"] == pytest.approx(
        cents_from_reference(row["f2"], row["f1"] * 3.0)
    )
    assert row["delta3_cents"] == pytest.approx(
        cents_from_reference(row["f3"], row["f1"] * 5.0)
    )


def test_cents_from_reference_matches_expected_formula() -> None:
    actual = cents_from_reference(762.0, 756.0)
    expected = 1200.0 * math.log2(762.0 / 756.0)

    assert actual == pytest.approx(expected)


def test_nearest_harmonic_multiple_uses_half_up_rounding() -> None:
    assert nearest_harmonic_multiple(2.5 * 100.0, 100.0) == 3


def test_extract_analysis_rows_keeps_case_without_detected_peaks() -> None:
    features_frame = pd.DataFrame(
        [
            {
                "case_id": "with_peak",
                "note": "open",
                "kind": "z_resonance",
                "index": 1,
                "frequency_hz": 300.0,
                "q_factor": 20.0,
                "amplitude": 4.0,
            }
        ]
    )
    case_frame = pd.DataFrame(
        [
            {"case_id": "with_peak", "note": "open", "primary_feature_family": "z_resonance"},
            {"case_id": "no_peak", "note": "closed", "primary_feature_family": "z_resonance"},
        ]
    )

    analysis_frame = extract_analysis_rows(features_frame, case_frame=case_frame)

    assert analysis_frame["case_id"].tolist() == ["no_peak", "with_peak"]
    missing_row = analysis_frame.loc[analysis_frame["case_id"] == "no_peak"].iloc[0]
    assert missing_row["feature_family"] == "z_resonance"
    assert pd.isna(missing_row["f1"])
