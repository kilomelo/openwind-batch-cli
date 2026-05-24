"""Integrated Tkinter dashboard for source-directory driven OpenWind studies."""

from __future__ import annotations

import argparse
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Sequence

import pandas as pd

from owbatch.config import BORE_TEMPLATE_FILENAME, CASES_FILENAME
from owbatch.response import build_response_frame
from owbatch.runner import BatchFrames, compute_batch_frames
from visulization.plot_analysis import (
    _ensure_matplotlib_cache_dirs,
    build_case_labels,
    prepare_analysis_plot_frame,
)
from visulization.view_analysis import (
    bind_analysis_cursor,
    resolve_selection_point_index,
)

_ensure_matplotlib_cache_dirs()

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import mplcursors

PLACEHOLDER_SELECT = "请选择包含源数据的目录"
PLACEHOLDER_INVALID = "源数据不满足要求"
PLACEHOLDER_LOADING = "正在计算，请稍候..."
PLACEHOLDER_NO_CASES = "请选择至少一个 case"


@dataclass(slots=True)
class StudyDirectoryLayout:
    """Validated study directory structure for the dashboard."""

    root_dir: Path
    template_dir: Path
    cases_path: Path


@dataclass(slots=True)
class DashboardFigureBundle:
    """Matplotlib figure plus cursor handles kept alive by the dashboard."""

    figure: Figure
    cursors: list[object]


@dataclass(slots=True)
class ResponseCursorSpec:
    """Per-line hover metadata for one embedded admittance chart."""

    frame: pd.DataFrame
    value_column: str
    value_label: str


@dataclass(slots=True)
class PitchCursorSpec:
    """Per-line hover metadata for one embedded pitch-frequency chart."""

    frame: pd.DataFrame
    peak_index: int


PEAK_FREQUENCY_COLUMN_PATTERN = re.compile(r"^f(\d+)$")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the desktop dashboard."""

    parser = argparse.ArgumentParser(
        prog="owbatch-dashboard",
        description=(
            "Open the integrated Tkinter dashboard for OpenWind batch studies. "
            "Choose a source directory containing template/ and cases.csv."
        ),
    )
    parser.add_argument(
        "--directory",
        type=Path,
        help="Optional source directory to load immediately on startup.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    root = tk.Tk()
    app = StudyDashboardApp(root)
    app.pack(fill="both", expand=True)
    if args.directory is not None:
        app.load_directory(Path(args.directory))
    root.mainloop()
    return 0


def resolve_study_directory(root_dir: Path) -> StudyDirectoryLayout:
    """Validate one source directory and return its canonical layout."""

    root_dir = Path(root_dir).expanduser().resolve()
    template_dir = root_dir / "template"
    cases_path = root_dir / CASES_FILENAME

    expected_paths = [cases_path, template_dir / BORE_TEMPLATE_FILENAME]
    missing_paths = [path for path in expected_paths if not path.exists()]
    if missing_paths:
        missing_display = ", ".join(str(path.relative_to(root_dir)) for path in missing_paths)
        raise ValueError(f"Missing required source files: {missing_display}")

    return StudyDirectoryLayout(
        root_dir=root_dir,
        template_dir=template_dir,
        cases_path=cases_path,
    )


def build_dashboard_figure(
    impedance_frame: pd.DataFrame,
    analysis_frame: pd.DataFrame,
) -> DashboardFigureBundle:
    """Build the four-chart study dashboard figure with mplcursors tooltips."""

    response_frame = build_response_frame(impedance_frame)
    if response_frame.empty:
        raise ValueError("No impedance rows are available for the dashboard.")

    figure = Figure(figsize=(12.6, 8.8), constrained_layout=True)
    grid = figure.add_gridspec(2, 2, width_ratios=(1.1, 1.0), height_ratios=(1.0, 1.0))
    modulus_axis = figure.add_subplot(grid[0, 0])
    angle_axis = figure.add_subplot(grid[1, 0], sharex=modulus_axis)
    pitch_axis = figure.add_subplot(grid[0, 1])
    analysis_axis = figure.add_subplot(grid[1, 1])

    response_frame = response_frame.reset_index(drop=True)
    response_cursors = _plot_admittance_axes(
        response_frame,
        modulus_axis=modulus_axis,
        angle_axis=angle_axis,
    )
    pitch_cursor = _plot_pitch_axis(
        analysis_frame,
        pitch_axis=pitch_axis,
    )
    analysis_cursor = _plot_analysis_axis(
        analysis_frame,
        analysis_axis=analysis_axis,
    )
    cursors = [*response_cursors]
    if pitch_cursor is not None:
        cursors.append(pitch_cursor)
    if analysis_cursor is not None:
        cursors.append(analysis_cursor)

    return DashboardFigureBundle(figure=figure, cursors=cursors)


def extract_case_ids(impedance_frame: pd.DataFrame) -> list[str]:
    """Return case ids in stable first-seen order from one impedance export."""

    ordered_case_ids = dict.fromkeys(impedance_frame["case_id"].astype(str).tolist())
    return list(ordered_case_ids)


def compute_toggled_case_selection(
    case_ids: list[str],
    selected_case_ids: set[str],
) -> set[str]:
    """Return the next selected-case set for the dashboard's toggle-all button."""

    if case_ids and set(case_ids).issubset(selected_case_ids):
        return set()
    return set(case_ids)


def filter_dashboard_frames(
    impedance_frame: pd.DataFrame,
    analysis_frame: pd.DataFrame,
    *,
    selected_case_ids: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter dashboard frames to only the selected case ids."""

    filtered_impedance = impedance_frame.loc[
        impedance_frame["case_id"].astype(str).isin(selected_case_ids)
    ].copy()
    filtered_analysis = analysis_frame.loc[
        analysis_frame["case_id"].astype(str).isin(selected_case_ids)
    ].copy()
    return filtered_impedance, filtered_analysis


def detect_populated_pitch_peak_indices(analysis_frame: pd.DataFrame) -> list[int]:
    """Return sorted peak indices whose `fN` columns contain at least one value."""

    indexed_peaks: list[int] = []
    for column in analysis_frame.columns:
        match = PEAK_FREQUENCY_COLUMN_PATTERN.match(str(column))
        if not match:
            continue
        if analysis_frame[column].notna().any():
            indexed_peaks.append(int(match.group(1)))
    indexed_peaks.sort()
    return indexed_peaks


def build_dashboard_export_path(root_dir: Path, now: datetime | None = None) -> Path:
    """Return one timestamped PNG path under the current study directory."""

    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    export_path = root_dir / f"{timestamp}.png"
    suffix = 1
    while export_path.exists():
        export_path = root_dir / f"{timestamp}_{suffix}.png"
        suffix += 1
    return export_path


def _plot_admittance_axes(
    response_frame: pd.DataFrame,
    *,
    modulus_axis,
    angle_axis,
) -> list[object]:
    series_keys = response_frame[["case_id", "note"]].astype(str).drop_duplicates()
    duplicate_case_ids = set(
        series_keys["case_id"].loc[
            series_keys["case_id"].duplicated(keep=False)
        ]
    )

    modulus_line_specs: dict[object, ResponseCursorSpec] = {}
    angle_line_specs: dict[object, ResponseCursorSpec] = {}
    for (case_id, note), case_frame in response_frame.groupby(["case_id", "note"], sort=False, dropna=False):
        case_frame = case_frame.sort_values("frequency_hz").reset_index(drop=True)
        line_label = _build_response_series_label(
            case_id=str(case_id),
            note=str(note or ""),
            duplicate_case_ids=duplicate_case_ids,
        )
        modulus_line = modulus_axis.plot(
            case_frame["frequency_hz"],
            case_frame["abs_y"],
            label=line_label,
            linewidth=1.5,
        )[0]
        angle_line = angle_axis.plot(
            case_frame["frequency_hz"],
            case_frame["angle_y_rad"],
            color=modulus_line.get_color(),
            linewidth=1.2,
        )[0]
        modulus_line.set_pickradius(8.0)
        angle_line.set_pickradius(8.0)
        modulus_line_specs[modulus_line] = ResponseCursorSpec(
            frame=case_frame,
            value_column="abs_y",
            value_label="|Y|",
        )
        angle_line_specs[angle_line] = ResponseCursorSpec(
            frame=case_frame,
            value_column="angle_y_rad",
            value_label="angle(Y) [rad]",
        )

    modulus_axis.set_ylabel("|Y|")
    modulus_axis.set_title("Admittance Modulus")
    modulus_axis.grid(True, alpha=0.3)
    modulus_axis.legend(title="case", loc="upper right")

    angle_axis.set_xlabel("Frequency (Hz)")
    angle_axis.set_ylabel("angle(Y) [rad]")
    angle_axis.set_title("Admittance Angle")
    angle_axis.grid(True, alpha=0.3)

    return [
        bind_response_cursor(modulus_line_specs),
        bind_response_cursor(angle_line_specs),
    ]


def _plot_analysis_axis(
    analysis_frame: pd.DataFrame,
    *,
    analysis_axis,
):
    if analysis_frame.empty:
        _render_empty_axis(
            analysis_axis,
            title="Harmonic Deviation",
            message="No analysis data",
            x_label="Case",
            y_label="Deviation [cents]",
        )
        return None

    try:
        plot_frame, delta_columns = prepare_analysis_plot_frame(analysis_frame)
    except ValueError:
        _render_empty_axis(
            analysis_axis,
            title="Harmonic Deviation",
            message="No populated deltaN_cents",
            x_label="Case",
            y_label="Deviation [cents]",
        )
        return None

    x_positions = list(range(len(plot_frame)))
    case_labels = build_case_labels(plot_frame)
    line_to_column: dict[object, str] = {}
    for column in delta_columns:
        line = analysis_axis.plot(
            x_positions,
            plot_frame[column],
            marker="o",
            linewidth=1.6,
            label=column,
        )[0]
        line.set_pickradius(8.0)
        line_to_column[line] = column

    analysis_axis.set_xticks(x_positions)
    analysis_axis.set_xticklabels(case_labels, rotation=30, ha="right")
    analysis_axis.set_xlabel("Case")
    analysis_axis.set_ylabel("Deviation [cents]")
    analysis_axis.set_title("Harmonic Deviation")
    analysis_axis.grid(True, alpha=0.3)
    analysis_axis.legend(title="Series", loc="upper right")
    return bind_analysis_cursor(plot_frame, line_to_column)


def _plot_pitch_axis(
    analysis_frame: pd.DataFrame,
    *,
    pitch_axis,
):
    if analysis_frame.empty:
        _render_empty_axis(
            pitch_axis,
            title="Pitch Frequency",
            message="No pitch data",
            x_label="Case",
            y_label="Frequency (Hz)",
        )
        return None

    plot_frame = analysis_frame.reset_index(drop=True)
    peak_indices = detect_populated_pitch_peak_indices(plot_frame)
    if not peak_indices:
        _render_empty_axis(
            pitch_axis,
            title="Pitch Frequency",
            message="No populated fN columns",
            x_label="Case",
            y_label="Frequency (Hz)",
        )
        return None

    x_positions = list(range(len(plot_frame)))
    case_labels = build_case_labels(plot_frame)
    line_specs: dict[object, PitchCursorSpec] = {}
    for peak_index in peak_indices:
        frequency_column = f"f{peak_index}"
        line = pitch_axis.plot(
            x_positions,
            plot_frame[frequency_column],
            marker="o",
            linewidth=1.6,
            label=frequency_column,
        )[0]
        line.set_pickradius(8.0)
        line_specs[line] = PitchCursorSpec(
            frame=plot_frame,
            peak_index=peak_index,
        )

    pitch_axis.set_xticks(x_positions)
    pitch_axis.set_xticklabels(case_labels, rotation=30, ha="right")
    pitch_axis.set_xlabel("Case")
    pitch_axis.set_ylabel("Frequency (Hz)")
    pitch_axis.set_title("Pitch Frequency")
    pitch_axis.grid(True, alpha=0.3)
    pitch_axis.legend(title="Series", loc="upper right")
    return bind_pitch_cursor(line_specs)


def bind_response_cursor(line_specs: dict[object, ResponseCursorSpec]):
    """Attach an mplcursors hover cursor to one response subplot."""

    cursor = mplcursors.cursor(
        list(line_specs),
        hover=mplcursors.HoverMode.Transient,
    )

    @cursor.connect("add")
    def _on_add(selection) -> None:
        spec = line_specs[selection.artist]
        point_index = resolve_selection_point_index(selection)
        row = spec.frame.iloc[point_index]
        selection.annotation.set_text(
            format_response_point_label(
                row,
                value_column=spec.value_column,
                value_label=spec.value_label,
            )
        )
        bbox_patch = selection.annotation.get_bbox_patch()
        if bbox_patch is not None:
            bbox_patch.set(boxstyle="round", fc="white", ec="0.6", alpha=0.95)
        if selection.annotation.arrow_patch is not None:
            selection.annotation.arrow_patch.set(arrowstyle="->", color="0.4")

    return cursor


def bind_pitch_cursor(line_specs: dict[object, PitchCursorSpec]):
    """Attach an mplcursors hover cursor to one pitch-frequency subplot."""

    cursor = mplcursors.cursor(
        list(line_specs),
        hover=mplcursors.HoverMode.Transient,
    )

    @cursor.connect("add")
    def _on_add(selection) -> None:
        spec = line_specs[selection.artist]
        point_index = resolve_selection_point_index(selection)
        row = spec.frame.iloc[point_index]
        selection.annotation.set_text(
            format_pitch_point_label(
                row,
                peak_index=spec.peak_index,
            )
        )
        bbox_patch = selection.annotation.get_bbox_patch()
        if bbox_patch is not None:
            bbox_patch.set(boxstyle="round", fc="white", ec="0.6", alpha=0.95)
        if selection.annotation.arrow_patch is not None:
            selection.annotation.arrow_patch.set(arrowstyle="->", color="0.4")

    return cursor


def format_response_point_label(
    row: pd.Series | dict[str, object],
    *,
    value_column: str,
    value_label: str,
) -> str:
    """Return a hover label for one admittance response point."""

    series = dict(row) if not isinstance(row, dict) else row
    case_id = str(series.get("case_id", ""))
    note = str(series.get("note", "") or "")
    lines = [f"case: {case_id}"]
    if note:
        lines.append(f"note: {note}")
    lines.append(f"frequency_hz: {float(series['frequency_hz']):.6f}")
    lines.append(f"{value_label}: {float(series[value_column]):.6f}")
    return "\n".join(lines)


def format_pitch_point_label(
    row: pd.Series | dict[str, object],
    *,
    peak_index: int,
) -> str:
    """Return a hover label for one pitch-frequency point."""

    series = dict(row) if not isinstance(row, dict) else row
    case_id = str(series.get("case_id", ""))
    note = str(series.get("note", "") or "")
    frequency_column = f"f{peak_index}"
    pitch_column = f"pitch{peak_index}"
    cents_column = f"pitch{peak_index}_cents"
    q_column = f"q{peak_index}"

    lines = [f"case: {case_id}"]
    if note:
        lines.append(f"note: {note}")
    lines.append(f"{frequency_column}: {float(series[frequency_column]):.6f} Hz")
    pitch_value = series.get(pitch_column)
    if pd.notna(pitch_value):
        lines.append(f"pitch: {str(pitch_value)}")
    pitch_cents_value = series.get(cents_column)
    if pd.notna(pitch_cents_value):
        lines.append(f"pitch_cents: {float(pitch_cents_value):.6f}")
    q_value = series.get(q_column)
    if pd.notna(q_value):
        lines.append(f"q: {float(q_value):.6f}")
    return "\n".join(lines)


def _build_response_series_label(
    *,
    case_id: str,
    note: str,
    duplicate_case_ids: set[str],
) -> str:
    if case_id in duplicate_case_ids and note:
        return f"{case_id}:{note}"
    return case_id


def _render_empty_axis(axis, *, title: str, message: str, x_label: str, y_label: str) -> None:
    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.grid(False)
    axis.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        transform=axis.transAxes,
        color="0.4",
    )


class StudyDashboardApp(ttk.Frame):
    """Desktop application shell for browsing one source directory at a time."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=12)
        self.master.title("owbatch Dashboard")
        self.master.geometry("1280x920")

        self._current_root_dir: Path | None = None
        self._current_batch: BatchFrames | None = None
        self._active_job_token = 0
        self._canvas: FigureCanvasTkAgg | None = None
        self._figure_bundle: DashboardFigureBundle | None = None
        self._case_vars: dict[str, tk.BooleanVar] = {}

        self.path_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=PLACEHOLDER_SELECT)
        self.placeholder_var = tk.StringVar(value=PLACEHOLDER_SELECT)
        self.case_toggle_button_var = tk.StringVar(value="全选")
        self.save_button: ttk.Button | None = None

        self._build_layout()
        self._show_placeholder(PLACEHOLDER_SELECT)

    def _build_layout(self) -> None:
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Button(controls, text="选择目录", command=self._choose_directory).pack(side="left")
        ttk.Button(controls, text="刷新", command=self.refresh_current_directory).pack(side="left", padx=(8, 0))
        self.save_button = ttk.Button(
            controls,
            text="保存图表",
            command=self.save_current_figure,
            state="disabled",
        )
        self.save_button.pack(side="left", padx=(8, 0))
        ttk.Entry(
            controls,
            textvariable=self.path_var,
            state="readonly",
        ).pack(side="left", fill="x", expand=True, padx=(12, 0))

        ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill="both", expand=True)

        self.case_panel = ttk.LabelFrame(self.content_frame, text="Cases", width=220)
        self.case_panel.pack(side="left", fill="y", padx=(0, 12))
        self.case_panel.pack_propagate(False)

        case_controls = ttk.Frame(self.case_panel)
        case_controls.pack(fill="x", padx=6, pady=(6, 0))
        self.case_toggle_button = ttk.Button(
            case_controls,
            textvariable=self.case_toggle_button_var,
            command=self.toggle_all_cases,
            state="disabled",
        )
        self.case_toggle_button.pack(fill="x")

        self.case_canvas = tk.Canvas(
            self.case_panel,
            highlightthickness=0,
            borderwidth=0,
        )
        self.case_scrollbar = ttk.Scrollbar(
            self.case_panel,
            orient="vertical",
            command=self.case_canvas.yview,
        )
        self.case_list_frame = ttk.Frame(self.case_canvas)
        self.case_canvas.configure(yscrollcommand=self.case_scrollbar.set)
        self._case_list_window = self.case_canvas.create_window(
            (0, 0),
            window=self.case_list_frame,
            anchor="nw",
        )
        self.case_list_frame.bind("<Configure>", self._on_case_list_frame_configure)
        self.case_canvas.bind("<Configure>", self._on_case_canvas_configure)
        self.case_canvas.pack(side="left", fill="both", expand=True)
        self.case_scrollbar.pack(side="right", fill="y")

        self.chart_host = ttk.Frame(self.content_frame)
        self.chart_host.pack(side="left", fill="both", expand=True)

        self.placeholder_label = ttk.Label(
            self.chart_host,
            textvariable=self.placeholder_var,
            anchor="center",
            justify="center",
            font=("TkDefaultFont", 13),
            foreground="#555555",
        )

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(
            title="Select Study Directory",
            mustexist=True,
        )
        if selected:
            self.load_directory(Path(selected))

    def load_directory(self, root_dir: Path) -> None:
        self._current_root_dir = Path(root_dir).expanduser()
        self.path_var.set(str(self._current_root_dir))
        self.status_var.set(f"已选择目录：{self._current_root_dir}")
        self._schedule_refresh()

    def refresh_current_directory(self) -> None:
        if self._current_root_dir is None:
            self._show_placeholder(PLACEHOLDER_SELECT)
            self.status_var.set(PLACEHOLDER_SELECT)
            return
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._current_root_dir is None:
            return

        try:
            layout = resolve_study_directory(self._current_root_dir)
        except ValueError as exc:
            self._current_batch = None
            self._set_case_selection_state([])
            self.status_var.set(str(exc))
            self._show_placeholder(PLACEHOLDER_INVALID)
            return

        self._active_job_token += 1
        job_token = self._active_job_token
        self.status_var.set(f"正在计算…… {layout.root_dir}")
        self._current_batch = None
        self._set_case_selection_state([])
        self._show_placeholder(PLACEHOLDER_LOADING)
        worker = threading.Thread(
            target=self._compute_dashboard_data,
            args=(layout, job_token),
            daemon=True,
        )
        worker.start()

    def _compute_dashboard_data(self, layout: StudyDirectoryLayout, job_token: int) -> None:
        def _progress_callback(completed: int, total: int, case_id: str) -> None:
            self.after(
                0,
                self._update_compute_progress,
                job_token,
                layout.root_dir,
                completed,
                total,
                case_id,
            )

        try:
            batch = compute_batch_frames(
                template_dir=layout.template_dir,
                cases_path=layout.cases_path,
                progress_callback=_progress_callback,
            )
        except Exception as exc:
            self.after(0, self._finish_compute_with_error, job_token, str(exc))
            return

        self.after(0, self._finish_compute_success, job_token, layout, batch)

    def _update_compute_progress(
        self,
        job_token: int,
        root_dir: Path,
        completed: int,
        total: int,
        case_id: str,
    ) -> None:
        if job_token != self._active_job_token:
            return

        if case_id:
            self.status_var.set(
                f"正在计算…… {completed}/{total} 条 case：{root_dir}（当前：{case_id}）"
            )
            return
        self.status_var.set(f"正在计算…… {completed}/{total} 条 case：{root_dir}")

    def _finish_compute_with_error(self, job_token: int, message: str) -> None:
        if job_token != self._active_job_token:
            return
        self._current_batch = None
        self._set_case_selection_state([])
        self.status_var.set(message)
        self._show_placeholder(PLACEHOLDER_INVALID)

    def _finish_compute_success(
        self,
        job_token: int,
        layout: StudyDirectoryLayout,
        batch: BatchFrames,
    ) -> None:
        if job_token != self._active_job_token:
            return

        self._current_batch = batch
        self._set_case_selection_state(
            extract_case_ids(batch.impedance_frame),
            preserve_existing=True,
        )
        self._redraw_selected_cases(layout=layout)

    def _render_figure_bundle(self, figure_bundle: DashboardFigureBundle) -> None:
        self._destroy_current_canvas()
        self.placeholder_label.place_forget()

        canvas = FigureCanvasTkAgg(figure_bundle.figure, master=self.chart_host)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        self._canvas = canvas
        self._figure_bundle = figure_bundle
        self._set_save_button_enabled(True)

    def _show_placeholder(self, message: str) -> None:
        self._destroy_current_canvas()
        self.placeholder_var.set(message)
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
        self._set_save_button_enabled(False)

    def _destroy_current_canvas(self) -> None:
        if self._canvas is not None:
            widget = self._canvas.get_tk_widget()
            widget.destroy()
            self._canvas = None
        self._figure_bundle = None

    def _set_case_selection_state(
        self,
        case_ids: list[str],
        *,
        preserve_existing: bool = False,
    ) -> None:
        previous_values = {
            case_id: var.get()
            for case_id, var in self._case_vars.items()
        } if preserve_existing else {}
        self._case_vars = {}
        for child in self.case_list_frame.winfo_children():
            child.destroy()

        for case_id in case_ids:
            is_selected = previous_values.get(case_id, True)
            case_var = tk.BooleanVar(value=is_selected)
            self._case_vars[case_id] = case_var
            ttk.Checkbutton(
                self.case_list_frame,
                text=case_id,
                variable=case_var,
                command=self._handle_case_selection_changed,
            ).pack(fill="x", anchor="w", padx=6, pady=2)
        self._update_case_toggle_button_state()

    def _selected_case_ids(self) -> set[str]:
        return {
            case_id
            for case_id, case_var in self._case_vars.items()
            if case_var.get()
        }

    def _handle_case_selection_changed(self) -> None:
        self._update_case_toggle_button_state()
        self._redraw_selected_cases()

    def toggle_all_cases(self) -> None:
        case_ids = list(self._case_vars)
        next_selection = compute_toggled_case_selection(
            case_ids,
            self._selected_case_ids(),
        )
        for case_id, case_var in self._case_vars.items():
            case_var.set(case_id in next_selection)
        self._update_case_toggle_button_state()
        self._redraw_selected_cases()

    def _redraw_selected_cases(self, *, layout: StudyDirectoryLayout | None = None) -> None:
        if self._current_batch is None:
            return

        selected_case_ids = self._selected_case_ids()
        if not selected_case_ids:
            self._show_placeholder(PLACEHOLDER_NO_CASES)
            if self._current_root_dir is not None:
                self.status_var.set(
                    f"未选择 case：{self._current_root_dir}"
                )
            return

        filtered_impedance, filtered_analysis = filter_dashboard_frames(
            self._current_batch.impedance_frame,
            self._current_batch.analysis_frame,
            selected_case_ids=selected_case_ids,
        )
        try:
            figure_bundle = build_dashboard_figure(
                filtered_impedance,
                filtered_analysis,
            )
        except Exception as exc:
            self.status_var.set(str(exc))
            self._show_placeholder(PLACEHOLDER_INVALID)
            return

        self._render_figure_bundle(figure_bundle)
        layout_root = layout.root_dir if layout is not None else self._current_root_dir
        if layout_root is not None:
            self.status_var.set(
                f"已显示 {len(selected_case_ids)} / {len(self._case_vars)} 个 case：{layout_root}"
            )

    def save_current_figure(self) -> None:
        if self._figure_bundle is None or self._current_root_dir is None:
            return

        export_path = build_dashboard_export_path(self._current_root_dir)
        self._figure_bundle.figure.savefig(export_path, dpi=150)
        self.status_var.set(f"图表已保存：{export_path}")

    def _on_case_list_frame_configure(self, _event) -> None:
        self.case_canvas.configure(scrollregion=self.case_canvas.bbox("all"))

    def _on_case_canvas_configure(self, event) -> None:
        self.case_canvas.itemconfigure(self._case_list_window, width=event.width)

    def _update_case_toggle_button_state(self) -> None:
        case_ids = list(self._case_vars)
        if not case_ids:
            self.case_toggle_button_var.set("全选")
            self.case_toggle_button.configure(state="disabled")
            return

        self.case_toggle_button.configure(state="normal")
        all_selected = set(case_ids).issubset(self._selected_case_ids())
        self.case_toggle_button_var.set("全不选" if all_selected else "全选")

    def _set_save_button_enabled(self, enabled: bool) -> None:
        if self.save_button is None:
            return
        self.save_button.configure(state="normal" if enabled else "disabled")


if __name__ == "__main__":
    raise SystemExit(main())
