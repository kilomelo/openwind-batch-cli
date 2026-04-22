from __future__ import annotations

from pathlib import Path

from owbatch.cli import main as owbatch_main
from visulization.plot_impedance import main as plot_main

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "basic_instrument"


def test_plot_impedance_cli_writes_png(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plot_path = tmp_path / "plots" / "impedance_abs_z.png"

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
            "--y-column",
            "abs_z",
        ]
    )

    assert plot_exit_code == 0
    assert plot_path.exists()
    assert plot_path.stat().st_size > 0
