from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from owbatch.config import BORE_TEMPLATE_FILENAME, CASES_FILENAME, TEMPLATE_FILENAMES
from visulization.study_dashboard import (
    DashboardFigureBundle,
    build_dashboard_export_path,
    build_dashboard_figure,
    compute_toggled_case_selection,
    detect_populated_pitch_peak_indices,
    extract_case_ids,
    filter_dashboard_frames,
    format_pitch_point_label,
    resolve_study_directory,
)


def test_resolve_study_directory_accepts_expected_layout(tmp_path: Path) -> None:
    source_dir = tmp_path / "study"
    template_dir = source_dir / "template"
    template_dir.mkdir(parents=True)
    (source_dir / CASES_FILENAME).write_text("case_id,note,f_start,f_stop,f_step\n", encoding="utf-8")
    for filename in TEMPLATE_FILENAMES:
        (template_dir / filename).write_text("", encoding="utf-8")

    layout = resolve_study_directory(source_dir)

    assert layout.root_dir == source_dir.resolve()
    assert layout.template_dir == template_dir.resolve()
    assert layout.cases_path == (source_dir / CASES_FILENAME).resolve()


def test_resolve_study_directory_rejects_missing_sources(tmp_path: Path) -> None:
    source_dir = tmp_path / "study"
    source_dir.mkdir()

    with pytest.raises(ValueError, match="Missing required source files"):
        resolve_study_directory(source_dir)


def test_resolve_study_directory_allows_missing_optional_holes_and_fingering_files(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "study"
    template_dir = source_dir / "template"
    template_dir.mkdir(parents=True)
    (source_dir / CASES_FILENAME).write_text("case_id,f_start,f_stop,f_step\n", encoding="utf-8")
    (template_dir / BORE_TEMPLATE_FILENAME).write_text("x0,x1,d0,d1,type\n", encoding="utf-8")

    layout = resolve_study_directory(source_dir)

    assert layout.root_dir == source_dir.resolve()


def test_build_dashboard_figure_renders_four_axes_and_cursors() -> None:
    impedance_frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_a", "case_b", "case_b"],
            "note": ["open", "open", "open", "open"],
            "frequency_hz": [100.0, 200.0, 100.0, 200.0],
            "re_z": [2.0, 1.0, 3.0, 1.5],
            "im_z": [0.5, -0.2, 0.4, -0.1],
            "player_preset": ["FLUTE", "FLUTE", "FLUTE", "FLUTE"],
        }
    )
    analysis_frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "note": ["open", "open"],
            "f1": [100.0, 102.0],
            "f2": [198.0, 205.0],
            "pitch1": ["G2", "G#2"],
            "pitch2": ["G3", "A3"],
            "pitch1_cents": [12.0, -8.0],
            "pitch2_cents": [4.0, -16.0],
            "q1": [32.0, 33.0],
            "q2": [54.0, 51.0],
            "h2": [1.98, 2.05],
            "delta2_cents": [-17.0, 42.0],
            "delta3_cents": [11.0, -8.0],
        }
    )

    bundle = build_dashboard_figure(impedance_frame, analysis_frame)

    assert isinstance(bundle, DashboardFigureBundle)
    assert len(bundle.figure.axes) == 4
    assert bundle.figure.axes[0].get_ylabel() == "|Y|"
    assert bundle.figure.axes[1].get_ylabel() == "angle(Y) [rad]"
    assert bundle.figure.axes[2].get_ylabel() == "Frequency (Hz)"
    assert bundle.figure.axes[3].get_ylabel() == "Deviation [cents]"
    assert len(bundle.cursors) == 4


def test_build_dashboard_figure_preserves_case_order_for_charts() -> None:
    impedance_frame = pd.DataFrame(
        {
            "case_id": ["case_2", "case_2", "case_10", "case_10", "case_1", "case_1"],
            "note": ["open", "open", "open", "open", "open", "open"],
            "frequency_hz": [200.0, 100.0, 200.0, 100.0, 200.0, 100.0],
            "re_z": [2.0, 1.0, 3.0, 1.5, 4.0, 2.5],
            "im_z": [0.5, -0.2, 0.4, -0.1, 0.3, -0.3],
            "player_preset": ["FLUTE", "FLUTE", "FLUTE", "FLUTE", "FLUTE", "FLUTE"],
        }
    )
    analysis_frame = pd.DataFrame(
        {
            "case_id": ["case_2", "case_10", "case_1"],
            "note": ["open", "open", "open"],
            "f1": [100.0, 102.0, 101.0],
            "f2": [198.0, 205.0, 201.0],
            "delta2_cents": [-17.0, 42.0, 11.0],
        }
    )

    bundle = build_dashboard_figure(impedance_frame, analysis_frame)

    assert [text.get_text() for text in bundle.figure.axes[0].get_legend().texts] == [
        "case_2",
        "case_10",
        "case_1",
    ]
    assert [text.get_text() for text in bundle.figure.axes[2].get_xticklabels()] == [
        "case_2",
        "case_10",
        "case_1",
    ]
    assert [text.get_text() for text in bundle.figure.axes[3].get_xticklabels()] == [
        "case_2",
        "case_10",
        "case_1",
    ]


def test_extract_case_ids_preserves_first_seen_order() -> None:
    impedance_frame = pd.DataFrame(
        {
            "case_id": ["case_b", "case_a", "case_b", "case_c"],
            "frequency_hz": [100.0, 100.0, 200.0, 100.0],
            "re_z": [1.0, 1.0, 1.0, 1.0],
            "im_z": [0.0, 0.0, 0.0, 0.0],
        }
    )

    assert extract_case_ids(impedance_frame) == ["case_b", "case_a", "case_c"]


def test_compute_toggled_case_selection_selects_all_then_clears_all() -> None:
    case_ids = ["case_a", "case_b", "case_c"]

    assert compute_toggled_case_selection(case_ids, {"case_a"}) == {
        "case_a",
        "case_b",
        "case_c",
    }
    assert compute_toggled_case_selection(case_ids, set(case_ids)) == set()


def test_build_dashboard_export_path_uses_timestamp_and_suffix(tmp_path: Path) -> None:
    first_path = build_dashboard_export_path(
        tmp_path,
        now=datetime(2026, 4, 27, 15, 4, 5),
    )
    assert first_path == tmp_path / "20260427_150405.png"

    first_path.write_text("occupied", encoding="utf-8")
    second_path = build_dashboard_export_path(
        tmp_path,
        now=datetime(2026, 4, 27, 15, 4, 5),
    )
    assert second_path == tmp_path / "20260427_150405_1.png"


def test_filter_dashboard_frames_limits_impedance_and_analysis_to_selected_cases() -> None:
    impedance_frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b", "case_c"],
            "frequency_hz": [100.0, 100.0, 100.0],
            "re_z": [1.0, 2.0, 3.0],
            "im_z": [0.0, 0.0, 0.0],
        }
    )
    analysis_frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b", "case_c"],
            "delta2_cents": [10.0, 20.0, 30.0],
        }
    )

    filtered_impedance, filtered_analysis = filter_dashboard_frames(
        impedance_frame,
        analysis_frame,
        selected_case_ids={"case_a", "case_c"},
    )

    assert filtered_impedance["case_id"].tolist() == ["case_a", "case_c"]
    assert filtered_analysis["case_id"].tolist() == ["case_a", "case_c"]


def test_detect_populated_pitch_peak_indices_uses_non_empty_f_columns() -> None:
    analysis_frame = pd.DataFrame(
        {
            "case_id": ["case_a", "case_b"],
            "f1": [100.0, 102.0],
            "f2": [198.0, 205.0],
            "f3": [None, None],
        }
    )

    assert detect_populated_pitch_peak_indices(analysis_frame) == [1, 2]


def test_format_pitch_point_label_includes_pitch_cents_and_q() -> None:
    row = pd.Series(
        {
            "case_id": "flute_probe",
            "note": "all_closed",
            "f2": 507.6099237983561,
            "pitch2": "B4",
            "pitch2_cents": 47.46010055443983,
            "q2": 141.0424788802406,
        }
    )

    label = format_pitch_point_label(row, peak_index=2)

    assert "case: flute_probe" in label
    assert "note: all_closed" in label
    assert "f2: 507.609924 Hz" in label
    assert "pitch: B4" in label
    assert "pitch_cents: 47.460101" in label
    assert "q: 141.042479" in label
