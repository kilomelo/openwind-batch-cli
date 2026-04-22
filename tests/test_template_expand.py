from __future__ import annotations

from pathlib import Path

from owbatch.case_expander import expand_cases
from owbatch.template_loader import load_template

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "basic_instrument"


def test_load_template_reads_rows_and_columns() -> None:
    template = load_template(FIXTURE_DIR)

    assert template.bore_columns == ["segment", "x0", "x1", "d0", "d1", "type", "param"]
    assert len(template.bore_rows) == 2
    assert template.bore_rows[0]["segment"] == "1"
    assert template.holes_rows[0]["label"] == "h1"
    assert list(template.fingering_rows[0].keys()) == ["label", "open", "closed"]


def test_expand_cases_applies_transforms_and_overrides() -> None:
    template = load_template(FIXTURE_DIR)

    expanded = expand_cases(template, FIXTURE_DIR / "cases.csv")

    assert [case.definition.case_id for case in expanded] == ["base", "variant"]

    base_case = expanded[0]
    variant_case = expanded[1]

    assert base_case.openwind_kwargs["compute_method"] == "TMM"
    assert variant_case.bore_rows[1]["d1"] == "21"
    assert variant_case.holes_rows[0]["position"] == "190"
    assert variant_case.holes_rows[1]["position"] == "242"
    assert variant_case.holes_rows[0]["diameter"] == "4.4"
    assert variant_case.holes_rows[1]["diameter"] == "4.95"


def test_expand_cases_maps_flute_type_to_player_preset(tmp_path: Path) -> None:
    template = load_template(FIXTURE_DIR)
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves,flute_type_instrument,source_location",
                "flute_probe,open,100,300,25,25,false,TMM,unflanged,false,true,entrance",
            ]
        ),
        encoding="utf-8",
    )

    expanded = expand_cases(template, cases_path)

    assert len(expanded) == 1
    assert expanded[0].openwind_kwargs["player_preset"] == "FLUTE"
    assert expanded[0].openwind_kwargs["source_location"] == "entrance"


def test_expand_cases_tolerates_trailing_empty_cells(tmp_path: Path) -> None:
    template = load_template(FIXTURE_DIR)
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves,bore_all_diameter_offset,all_hole_diameter_scale,upper_holes_shift",
                "base,open,100,300,25,25,false,TMM,unflanged,false,,,,,",
            ]
        ),
        encoding="utf-8",
    )

    expanded = expand_cases(template, cases_path)

    assert len(expanded) == 1
    assert expanded[0].definition.case_id == "base"
    assert expanded[0].definition.sweep is not None
    assert expanded[0].definition.sweep.f_step == 25.0


def test_expand_cases_rejects_unknown_note_name(tmp_path: Path) -> None:
    template = load_template(FIXTURE_DIR)
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        "\n".join(
            [
                "case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves",
                "base,unknown_note,100,300,25,25,false,TMM,unflanged,false",
            ]
        ),
        encoding="utf-8",
    )

    try:
        expand_cases(template, cases_path)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expand_cases should reject an unknown note name")

    assert "unknown_note" in message
    assert "available fingering notes" in message
