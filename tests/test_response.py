from __future__ import annotations

import numpy as np
import pandas as pd

from owbatch.response import (
    build_case_response_metadata,
    build_case_response_metadata_from_row,
    build_response_frame,
    infer_default_response_mode,
    infer_primary_feature_family,
    resolve_requested_response_mode,
)


def test_build_response_frame_derives_impedance_and_admittance_consistently() -> None:
    frame = pd.DataFrame(
        {
            "frequency_hz": [100.0, 200.0, 300.0],
            "re_z": [3.0, -4.0, 2.0],
            "im_z": [4.0, 3.0, -2.0],
        }
    )

    response = build_response_frame(frame)

    np.testing.assert_allclose(
        response["abs_y"].to_numpy(),
        1.0 / response["abs_z"].to_numpy(),
    )

    angle_sum = response["angle_y_rad"].to_numpy() + response["angle_z_rad"].to_numpy()
    wrapped = np.angle(np.exp(1j * angle_sum))
    np.testing.assert_allclose(wrapped, np.zeros_like(wrapped), atol=1e-12)


def test_build_response_frame_preserves_peak_valley_duality() -> None:
    frame = pd.DataFrame(
        {
            "frequency_hz": [100.0, 200.0, 300.0],
            "re_z": [5.0, 2.0, 6.0],
            "im_z": [0.0, 0.0, 0.0],
        }
    )

    response = build_response_frame(frame)

    impedance_valley_index = response["abs_z"].idxmin()
    admittance_peak_index = response["abs_y"].idxmax()

    assert impedance_valley_index == admittance_peak_index


def test_flute_like_semantics_default_to_admittance_family() -> None:
    assert infer_default_response_mode("FLUTE") == "admittance"
    assert infer_default_response_mode("SOPRANO_RECORDER") == "admittance"
    assert infer_default_response_mode("UNITARY_FLOW") == "impedance"

    assert infer_primary_feature_family("FLUTE") == "y_resonance"
    assert infer_primary_feature_family("UNITARY_FLOW") == "z_resonance"


def test_build_case_response_metadata_exposes_future_feature_hints() -> None:
    flute_metadata = build_case_response_metadata(player_preset="FLUTE")
    flow_metadata = build_case_response_metadata(player_preset=None)

    assert flute_metadata["player_preset"] == "FLUTE"
    assert flute_metadata["is_flute_like"] is True
    assert flute_metadata["default_response_mode"] == "admittance"
    assert flute_metadata["primary_feature_family"] == "y_resonance"

    assert flow_metadata["player_preset"] == "UNITARY_FLOW"
    assert flow_metadata["is_flute_like"] is False
    assert flow_metadata["default_response_mode"] == "impedance"
    assert flow_metadata["primary_feature_family"] == "z_resonance"


def test_build_case_response_metadata_from_row_reads_row_like_metadata() -> None:
    row_metadata = build_case_response_metadata_from_row({"player_preset": "soprano_recorder"})

    assert row_metadata["player_preset"] == "SOPRANO_RECORDER"
    assert row_metadata["default_response_mode"] == "admittance"
    assert row_metadata["primary_feature_family"] == "y_resonance"


def test_resolve_requested_response_mode_supports_auto_and_explicit_override() -> None:
    flute_frame = pd.DataFrame(
        {
            "frequency_hz": [100.0],
            "re_z": [1.0],
            "im_z": [0.0],
            "player_preset": ["FLUTE"],
        }
    )
    flow_frame = pd.DataFrame(
        {
            "frequency_hz": [100.0],
            "re_z": [1.0],
            "im_z": [0.0],
            "player_preset": ["UNITARY_FLOW"],
        }
    )

    assert resolve_requested_response_mode(flute_frame, requested_mode="auto") == "admittance"
    assert resolve_requested_response_mode(flow_frame, requested_mode="auto") == "impedance"
    assert resolve_requested_response_mode(flute_frame, requested_mode="impedance") == "impedance"
    assert resolve_requested_response_mode(flow_frame, requested_mode="admittance") == "admittance"
