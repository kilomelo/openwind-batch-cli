from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from owbatch.cli import main as owbatch_main
from visulization.plot_analysis import (
    detect_populated_delta_columns,
    main as plot_analysis_main,
    plot_analysis_frame,
)
from visulization.plot_impedance import (
    load_impedance_frame,
    main as plot_main,
    plot_response_frame,
)
from visulization.view_analysis import (
    bind_analysis_cursor,
    format_analysis_point_label,
    main as view_analysis_main,
    plot_interactive_analysis_frame,
    resolve_selection_point_index,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "basic_instrument"


def test_plot_impedance_cli_writes_png(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plot_path = tmp_path / "plots" / "admittance_response.png"

    exit_code = owbatch_main(
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

    plot_exit_code = plot_main(
        [
            "--input",
            str(out_dir / "impedance.csv"),
            "--output",
            str(plot_path),
            "--mode",
            "admittance",
            "--angle-unit",
            "deg",
        ]
    )

    assert plot_exit_code == 0
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0


def test_plot_response_frame_builds_two_semantic_axes(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    exit_code = owbatch_main(
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

    frame = load_impedance_frame(out_dir / "impedance.csv")
    figure = plot_response_frame(frame, mode="impedance", angle_unit="pi")

    assert len(figure.axes) == 2
    assert figure.axes[0].get_ylabel() == "|Z|"
    assert figure.axes[1].get_ylabel() == "angle(Z) / pi"


def test_plot_response_frame_auto_mode_uses_flute_metadata() -> None:
    frame = pd.DataFrame(
        {
            "case_id": ["flute_case", "flute_case"],
            "note": ["open", "open"],
            "frequency_hz": [100.0, 200.0],
            "re_z": [2.0, 1.0],
            "im_z": [0.0, 0.0],
            "player_preset": ["FLUTE", "FLUTE"],
        }
    )

    figure = plot_response_frame(frame, mode="auto", angle_unit="deg")

    assert figure.axes[0].get_ylabel() == "|Y|"
    assert figure.axes[1].get_ylabel() == "angle(Y) [deg]"


def test_plot_response_frame_explicit_mode_overrides_auto_semantics() -> None:
    frame = pd.DataFrame(
        {
            "case_id": ["flow_case", "flow_case"],
            "note": ["open", "open"],
            "frequency_hz": [100.0, 200.0],
            "re_z": [2.0, 1.0],
            "im_z": [0.0, 0.0],
            "player_preset": ["UNITARY_FLOW", "UNITARY_FLOW"],
        }
    )

    figure = plot_response_frame(frame, mode="admittance", angle_unit="rad")

    assert figure.axes[0].get_ylabel() == "|Y|"
    assert figure.axes[1].get_ylabel() == "angle(Y) [rad]"


def test_plot_analysis_cli_writes_png(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.csv"
    plot_path = tmp_path / "plots" / "analysis.png"
    pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "note": ["open", "open"],
            "delta2_cents": [12.0, 8.0],
            "delta3_cents": [21.0, 19.0],
        }
    ).to_csv(analysis_path, index=False)

    plot_exit_code = plot_analysis_main(
        [
            "--input",
            str(analysis_path),
            "--output",
            str(plot_path),
        ]
    )

    assert plot_exit_code == 0
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0


def test_detect_populated_delta_columns_handles_three_and_four_peak_schemas() -> None:
    three_peak_frame = pd.DataFrame(
        {
            "case_id": ["a", "b"],
            "delta2_cents": [10.0, 20.0],
            "delta3_cents": [30.0, 40.0],
        }
    )
    four_peak_frame = pd.DataFrame(
        {
            "case_id": ["a", "b"],
            "delta2_cents": [10.0, 20.0],
            "delta3_cents": [30.0, 40.0],
            "delta4_cents": [50.0, 60.0],
        }
    )

    assert detect_populated_delta_columns(three_peak_frame) == [
        "delta2_cents",
        "delta3_cents",
    ]
    assert detect_populated_delta_columns(four_peak_frame) == [
        "delta2_cents",
        "delta3_cents",
        "delta4_cents",
    ]


def test_plot_analysis_frame_draws_one_line_per_populated_delta_column() -> None:
    frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "note": ["open", "open"],
            "delta2_cents": [12.0, 8.0],
            "delta3_cents": [21.0, 19.0],
            "delta4_cents": [None, None],
        }
    )

    figure = plot_analysis_frame(frame)

    assert len(figure.axes) == 1
    assert figure.axes[0].get_ylabel() == "Deviation [cents]"
    assert len(figure.axes[0].lines) == 2


def test_plot_interactive_analysis_frame_builds_hoverable_lines() -> None:
    frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "note": ["open", "open"],
            "f2": [392.3, 401.2],
            "h2": [2.96, 3.03],
            "delta2_cents": [-22.1, 17.5],
            "delta3_cents": [12.0, 8.0],
        }
    )

    figure, cursor = plot_interactive_analysis_frame(frame)

    assert len(figure.axes) == 1
    assert figure.axes[0].get_ylabel() == "Deviation [cents]"
    assert len(figure.axes[0].lines) == 2
    assert hasattr(cursor, "connect")


def test_resolve_selection_point_index_picks_nearest_real_point() -> None:
    frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b", "case_c"],
            "note": ["open", "open", "open"],
            "delta2_cents": [10.0, 30.0, 5.0],
            "delta3_cents": [12.0, 20.0, 8.0],
        }
    )

    figure, _cursor = plot_interactive_analysis_frame(frame)
    line = figure.axes[0].lines[0]
    selection = SimpleNamespace(artist=line, target=(0.9, 28.0))

    assert resolve_selection_point_index(selection) == 1


def test_format_analysis_point_label_includes_exact_values() -> None:
    row = pd.Series(
        {
            "case_id": "flow_probe",
            "note": "all_closed",
            "f2": 392.3913282035871,
            "h2": 2.961790477916071,
            "delta2_cents": -22.1914982157585,
        }
    )

    label = format_analysis_point_label(row, "delta2_cents")

    assert "case: flow_probe" in label
    assert "note: all_closed" in label
    assert "delta2_cents: -22.191498" in label
    assert "f2: 392.391328 Hz" in label
    assert "h2: 2.961790 x f1" in label
    assert "nearest multiple: 3 x f1" in label


def test_view_analysis_main_opens_window(monkeypatch, tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.csv"
    pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "note": ["open", "open"],
            "delta2_cents": [12.0, 8.0],
            "delta3_cents": [21.0, 19.0],
        }
    ).to_csv(analysis_path, index=False)

    show_calls: list[bool] = []

    def fake_show() -> None:
        show_calls.append(True)

    monkeypatch.setattr("visulization.view_analysis.plt.show", fake_show)

    exit_code = view_analysis_main(["--input", str(analysis_path)])

    assert exit_code == 0
    assert show_calls == [True]
