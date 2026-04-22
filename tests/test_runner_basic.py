from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from owbatch.cli import main
from owbatch.config import ANALYSIS_COLUMNS, FEATURE_COLUMNS, IMPEDANCE_COLUMNS

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
    assert len(impedance_frame) == 18
    assert (impedance_frame["abs_z"] > 0).all()

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

    assert flow_abs_z.shape == flute_abs_z.shape
    assert flow_abs_z.size > 0
    assert not np.allclose(flow_abs_z, flute_abs_z)
