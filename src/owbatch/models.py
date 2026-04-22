"""Data models for owbatch.

These classes intentionally describe the target IO schema before the actual
template loading and OpenWind integration are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CsvRow = dict[str, str]
CsvTable = list[CsvRow]


@dataclass(slots=True)
class TemplateManifest:
    """Expected template file locations inside one template directory."""

    template_dir: Path
    bore_path: Path
    holes_path: Path
    fingering_path: Path


@dataclass(slots=True)
class FrequencySweep:
    """Frequency-domain sweep settings for one case."""

    f_start: float
    f_stop: float
    f_step: float


@dataclass(slots=True)
class SolverSettings:
    """OpenWind-facing solver settings kept as a stable internal schema."""

    temperature_c: float | None = None
    losses: bool | str | None = None
    compute_method: str | None = None
    radiation_category: str | None = None
    spherical_waves: bool | str | None = None
    player_preset: str | None = None
    source_location: str | None = None


@dataclass(slots=True)
class CaseDefinition:
    """Normalized view of one row from cases.csv."""

    case_id: str
    note: str | None = None
    sweep: FrequencySweep | None = None
    solver: SolverSettings = field(default_factory=SolverSettings)
    geometry_overrides: dict[str, str] = field(default_factory=dict)
    transform_fields: dict[str, str] = field(default_factory=dict)
    raw_fields: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class LoadedTemplate:
    """In-memory representation of the three template CSV files."""

    manifest: TemplateManifest
    bore_columns: list[str] = field(default_factory=list)
    holes_columns: list[str] = field(default_factory=list)
    fingering_columns: list[str] = field(default_factory=list)
    bore_rows: CsvTable = field(default_factory=list)
    holes_rows: CsvTable = field(default_factory=list)
    fingering_rows: CsvTable = field(default_factory=list)


@dataclass(slots=True)
class ExpandedCase:
    """Fully expanded case ready for later OpenWind execution."""

    definition: CaseDefinition
    bore_rows: CsvTable = field(default_factory=list)
    holes_rows: CsvTable = field(default_factory=list)
    fingering_rows: CsvTable = field(default_factory=list)
    openwind_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InspectRequest:
    """CLI request for inspecting template + cases inputs."""

    template_dir: Path
    cases_path: Path


@dataclass(slots=True)
class RunRequest:
    """CLI request for executing a batch run."""

    template_dir: Path
    cases_path: Path
    out_dir: Path
