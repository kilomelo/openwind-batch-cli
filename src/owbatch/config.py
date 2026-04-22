"""Static configuration shared across the CLI and pipeline modules."""

from __future__ import annotations

from pathlib import Path

PACKAGE_NAME = "owbatch"
GEOMETRY_UNIT = "mm"

BORE_TEMPLATE_FILENAME = "bore_template.csv"
HOLES_TEMPLATE_FILENAME = "holes_template.csv"
FINGERING_TEMPLATE_FILENAME = "fingering_template.csv"

TEMPLATE_FILENAMES = (
    BORE_TEMPLATE_FILENAME,
    HOLES_TEMPLATE_FILENAME,
    FINGERING_TEMPLATE_FILENAME,
)

BORE_TEMPLATE_REQUIRED_COLUMNS = (
    "x0",
    "x1",
    "d0",
    "d1",
    "type",
)

HOLES_TEMPLATE_REQUIRED_COLUMNS = (
    "label",
    "position",
    "length",
    "diameter",
)

FINGERING_TEMPLATE_REQUIRED_COLUMNS = ("label",)

OUTPUT_IMPEDANCE_FILENAME = "impedance.csv"
OUTPUT_FEATURES_FILENAME = "features.csv"
OUTPUT_ANALYSIS_FILENAME = "analysis.csv"
OUTPUT_IMPEDANCE_LISTS_DIRNAME = "impedances"

OUTPUT_FILENAMES = (
    OUTPUT_IMPEDANCE_FILENAME,
    OUTPUT_FEATURES_FILENAME,
    OUTPUT_ANALYSIS_FILENAME,
)

RESERVED_CASE_COLUMNS = {
    "case_id",
    "note",
    "f_start",
    "f_stop",
    "f_step",
    "temperature_c",
    "losses",
    "compute_method",
    "radiation_category",
    "spherical_waves",
    "flute_type_instrument",
    "player_preset",
    "source_location",
}

DERIVED_CASE_COLUMNS = {
    "bore_all_diameter_offset",
    "all_hole_diameter_scale",
    "upper_holes_shift",
}

BOOL_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
BOOL_FALSE_VALUES = {"0", "false", "no", "n", "off"}

IMPEDANCE_COLUMNS = (
    "case_id",
    "note",
    "frequency_hz",
    "re_z",
    "im_z",
    "abs_z",
    "angle_z_rad",
    "angle_z_deg",
    "abs_y",
    "angle_y_rad",
    "angle_y_deg",
)

FEATURE_COLUMNS = (
    "case_id",
    "note",
    "kind",
    "index",
    "frequency_hz",
    "q_factor",
    "amplitude",
    "abs_z",
    "angle_z_deg",
    "abs_y",
    "angle_y_deg",
)

ANALYSIS_COLUMNS = (
    "case_id",
    "note",
    "f1",
    "f2",
    "f3",
    "f4",
    "h2",
    "h3",
    "h4",
    "delta2_cents",
    "delta3_cents",
    "delta4_cents",
    "q1",
    "q2",
    "q3",
    "a1",
    "a2",
    "a3",
)


def build_output_paths(out_dir: Path) -> dict[str, Path]:
    """Return the default CSV outputs for one batch run."""

    return {
        "impedance": out_dir / OUTPUT_IMPEDANCE_FILENAME,
        "features": out_dir / OUTPUT_FEATURES_FILENAME,
        "analysis": out_dir / OUTPUT_ANALYSIS_FILENAME,
        "impedance_lists_dir": out_dir / OUTPUT_IMPEDANCE_LISTS_DIRNAME,
    }
