from __future__ import annotations

from pathlib import Path

from owbatch.cli import main as owbatch_main
from visulization.plot_impedance import (
    load_impedance_frame,
    main as plot_main,
    plot_response_frame,
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
