from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from owbatch.cli import main
from owbatch.config import ANALYSIS_COLUMNS, FEATURE_COLUMNS, IMPEDANCE_COLUMNS
from owbatch.runner import compute_batch_frames

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "basic_instrument"


def test_inspect_command_outputs_expanded_json(
    capsys,
) -> None:
    exit_code = main(
        [
            "inspect",
            "--template-dir",
            str(FIXTURE_DIR),
            "--cases",
            str(FIXTURE_DIR / "cases.csv"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["template"]["bore_rows"][0]["segment"] == "1"
    assert len(payload["expanded_cases"]) == 2
    assert payload["expanded_cases"][1]["openwind_kwargs"]["compute_method"] == "TMM"


def test_run_command_writes_impedance_csv(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "run",
            "--template-dir",
            str(FIXTURE_DIR),
            "--cases",
            str(FIXTURE_DIR / "cases.csv"),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert exit_code == 0

    impedance_frame = pd.read_csv(out_dir / "impedance.csv")
    features_frame = pd.read_csv(out_dir / "features.csv")
    analysis_frame = pd.read_csv(out_dir / "analysis.csv")

    assert tuple(impedance_frame.columns) == IMPEDANCE_COLUMNS
    assert tuple(features_frame.columns) == FEATURE_COLUMNS
    assert tuple(analysis_frame.columns) == ANALYSIS_COLUMNS
    assert set(impedance_frame["case_id"]) == {"base", "variant"}
    assert set(impedance_frame["note"]) == {"open", "closed"}
    assert set(impedance_frame["player_preset"]) == {"UNITARY_FLOW"}
    assert set(impedance_frame["default_response_mode"]) == {"impedance"}
    assert set(impedance_frame["primary_feature_family"]) == {"z_resonance"}
    assert len(impedance_frame) == 18
    assert (impedance_frame["abs_z"] > 0).all()
    if not features_frame.empty:
        assert (features_frame["q_factor"] > 0).all()
        assert set(features_frame["kind"]) == {"z_resonance"}
    assert len(analysis_frame) == 2
    assert set(analysis_frame["feature_family"]) == {"z_resonance"}
    populated_analysis = analysis_frame["f1"].notna()
    assert populated_analysis.any()
    assert analysis_frame.loc[populated_analysis, "pitch1"].astype(str).str.len().gt(0).all()
    assert analysis_frame.loc[populated_analysis, "q1"].notna().all()
    assert analysis_frame.loc[populated_analysis, "a1"].notna().all()
    populated_harmonics = analysis_frame["f2"].notna()
    if populated_harmonics.any():
        ratios = analysis_frame.loc[populated_harmonics, "f2"] / analysis_frame.loc[populated_harmonics, "f1"]
        assert np.allclose(
            analysis_frame.loc[populated_harmonics, "h2"],
            ratios,
        )
        nearest_multiples = np.maximum(
            1,
            np.floor(ratios.to_numpy(dtype=float) + 0.5).astype(int),
        )
        expected_delta = 1200.0 * np.log2(
            analysis_frame.loc[populated_harmonics, "f2"]
            / (
                analysis_frame.loc[populated_harmonics, "f1"]
                * nearest_multiples
            )
        )
        assert np.allclose(
            analysis_frame.loc[populated_harmonics, "delta2_cents"].to_numpy(dtype=float),
            expected_delta.to_numpy(dtype=float),
        )

    base_list = out_dir / "impedances" / "base.csv"
    variant_list = out_dir / "impedances" / "variant.csv"

    assert base_list.exists()
    assert variant_list.exists()

    base_lines = base_list.read_text(encoding="utf-8").splitlines()
    assert base_lines[0] == "#case_id:base; note:open"
    assert base_lines[1] == "#f[Hz] abs(Y) angle(Y)[rad]"
    assert len(base_lines) == 11

    sample_parts = base_lines[2].split()
    assert len(sample_parts) == 3
    assert re.match(r"^\d+(?:\.\d+)?$", sample_parts[0])
    assert re.match(r"^[+-]?\d\.\d+e[+-]\d+$", sample_parts[1])
    assert re.match(r"^[+-]?\d\.\d+e[+-]\d+$", sample_parts[2])

    float(sample_parts[0])
    float(sample_parts[1])
    float(sample_parts[2])


def test_run_command_supports_flute_player_preset(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.csv"
    out_dir = tmp_path / "out"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves,flute_type_instrument",
                "flow_case,open,100,300,25,25,false,TMM,unflanged,false,false",
                "flute_case,open,100,300,25,25,false,TMM,unflanged,false,true",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
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
    flow_abs_z = impedance_frame.loc[impedance_frame["case_id"] == "flow_case", "abs_z"].to_numpy()
    flute_abs_z = impedance_frame.loc[impedance_frame["case_id"] == "flute_case", "abs_z"].to_numpy()
    flute_modes = set(
        impedance_frame.loc[
            impedance_frame["case_id"] == "flute_case",
            "default_response_mode",
        ]
    )
    flute_feature_families = set(
        impedance_frame.loc[
            impedance_frame["case_id"] == "flute_case",
            "primary_feature_family",
        ]
    )

    assert flow_abs_z.shape == flute_abs_z.shape
    assert flow_abs_z.size > 0
    assert not np.allclose(flow_abs_z, flute_abs_z)
    assert flute_modes == {"admittance"}
    assert flute_feature_families == {"y_resonance"}


def test_run_command_supports_holeless_instrument_with_missing_optional_templates(
    tmp_path: Path,
) -> None:
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "bore_template.csv").write_text(
        "\n".join(
            [
                "x0,x1,d0,d1,type",
                "0,500,20,20,linear",
            ]
        ),
        encoding="utf-8",
    )
    cases_path = tmp_path / "cases.csv"
    out_dir = tmp_path / "out"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves",
                "no_holes,100,400,25,25,false,TMM,unflanged,false",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--template-dir",
            str(template_dir),
            "--cases",
            str(cases_path),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert exit_code == 0

    impedance_frame = pd.read_csv(out_dir / "impedance.csv")
    assert set(impedance_frame["case_id"]) == {"no_holes"}
    assert len(impedance_frame) > 0


def test_run_command_supports_holeless_instrument_with_empty_optional_tables_and_note(
    tmp_path: Path,
) -> None:
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "bore_template.csv").write_text(
        "\n".join(
            [
                "x0,x1,d0,d1,type",
                "0,500,20,20,linear",
            ]
        ),
        encoding="utf-8",
    )
    (template_dir / "holes_template.csv").write_text(
        "label,position,length,diameter\n",
        encoding="utf-8",
    )
    (template_dir / "fingering_template.csv").write_text(
        "label\n",
        encoding="utf-8",
    )
    cases_path = tmp_path / "cases.csv"
    out_dir = tmp_path / "out"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves",
                "no_holes_with_note,G4,100,400,25,25,false,TMM,unflanged,false",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "run",
            "--template-dir",
            str(template_dir),
            "--cases",
            str(cases_path),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert exit_code == 0

    impedance_frame = pd.read_csv(out_dir / "impedance.csv")
    assert set(impedance_frame["case_id"]) == {"no_holes_with_note"}
    assert set(impedance_frame["note"]) == {"G4"}
    assert len(impedance_frame) > 0


def test_compute_batch_frames_reports_case_progress() -> None:
    progress_events: list[tuple[int, int, str]] = []

    batch = compute_batch_frames(
        template_dir=FIXTURE_DIR,
        cases_path=FIXTURE_DIR / "cases.csv",
        progress_callback=lambda completed, total, case_id: progress_events.append(
            (completed, total, case_id)
        ),
    )

    assert len(batch.expanded_cases) == 2
    assert progress_events == [
        (0, 2, ""),
        (1, 2, "base"),
        (2, 2, "variant"),
    ]
