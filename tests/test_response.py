from __future__ import annotations

import numpy as np
import pandas as pd

from owbatch.response import (
    build_response_frame,
    infer_default_response_mode,
    infer_primary_feature_family,
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
