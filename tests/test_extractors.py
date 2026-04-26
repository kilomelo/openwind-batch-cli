from __future__ import annotations

from pathlib import Path

import pandas as pd

from owbatch.cli import main as owbatch_main
from owbatch.extractors import extract_frequency_features

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "basic_instrument"


def test_extract_frequency_features_defaults_to_three_primary_peaks(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.csv"
    out_dir = tmp_path / "out"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves,flute_type_instrument",
                "flow_case,open,100,2000,5,25,false,TMM,unflanged,false,false",
                "flute_case,open,100,2000,5,25,false,TMM,unflanged,false,true",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = owbatch_main(
        [
            "run",
            "--template-dir",
            str(FIXTURE_DIR),
            "--cases",
            str(cases_path),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert exit_code == 0

    features_frame = pd.read_csv(out_dir / "features.csv")

    assert set(features_frame["case_id"]) == {"flow_case", "flute_case"}
    assert features_frame.groupby("case_id").size().to_dict() == {
        "flow_case": 3,
        "flute_case": 3,
    }
    assert set(features_frame.loc[features_frame["case_id"] == "flow_case", "kind"]) == {
        "z_resonance"
    }
    assert set(features_frame.loc[features_frame["case_id"] == "flute_case", "kind"]) == {
        "y_resonance"
    }
    assert (features_frame["q_factor"] > 0).all()
    assert features_frame.groupby("case_id")["frequency_hz"].apply(lambda s: s.is_monotonic_increasing).all()


def test_extract_frequency_features_respects_peak_count_override(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.csv"
    out_dir = tmp_path / "out"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves",
                "flow_case,open,100,2000,5,25,false,TMM,unflanged,false",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = owbatch_main(
        [
            "run",
            "--template-dir",
            str(FIXTURE_DIR),
            "--cases",
            str(cases_path),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert exit_code == 0

    impedance_frame = pd.read_csv(out_dir / "impedance.csv")
    features_frame = extract_frequency_features(impedance_frame, peak_count=2)

    assert len(features_frame) == 2
    assert list(features_frame["index"]) == [1, 2]
