from __future__ import annotations

import pytest

from owbatch.cli import build_parser, main


def test_parser_has_expected_subcommands() -> None:
    parser = build_parser()

    inspect_args = parser.parse_args(
        ["inspect", "--template-dir", "templates/base", "--cases", "cases.csv"]
    )
    run_args = parser.parse_args(
        [
            "run",
            "--template-dir",
            "templates/base",
            "--cases",
            "cases.csv",
            "--out-dir",
            "out",
        ]
    )

    assert inspect_args.command == "inspect"
    assert run_args.command == "run"


def test_main_help_lists_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "inspect" in output
    assert "run" in output
