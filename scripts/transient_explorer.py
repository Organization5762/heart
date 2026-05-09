#!/usr/bin/env python3
"""Interactive transient explorer for local audio files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import numpy as np
import sounddevice as sd

from heart.utilities.transients import (
    DEFAULT_FRAME_SIZE,
    DEFAULT_HOP_SIZE,
    DEFAULT_MIN_SPACING_MS,
    DEFAULT_THRESHOLD_SCALE,
    DEFAULT_THRESHOLD_WINDOW_SECONDS,
    TransientAnalysis,
    analyze_transients,
)

AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aiff", ".aif", ".flac", ".ogg"}
DEFAULT_SAMPLE_RATE = 22_050
DEFAULT_CHANNELS = 2
_PLAYHEAD_COLOR = "#ff867f"
_TRANSIENT_BASS_COLOR = "#5ed0c2"
_LOW_BAND_COLOR = "#88f0a8"
_SECONDARY_PANEL_COLOR = "#f7a8b8"
_GRID_COLOR = "#2c3242"
_BACKGROUND_COLOR = "#101419"
_PLOT_LEFT_GUTTER = 72
_PLOT_RIGHT_GUTTER = 16


@dataclass(frozen=True, slots=True)
class ExplorerConfig:
    sample_rate: int
    frame_size: int
    hop_size: int
    threshold_window_seconds: float
    threshold_scale: float
    min_spacing_ms: float


PANEL_MODE_LABELS = {
    "energy": "Selected Range Energy + Threshold",
    "raw_flux": "Raw Flux (Debug)",
}


@dataclass(slots=True)
class LoadedTrack:
    path: Path
    playback_samples: np.ndarray
    analysis: TransientAnalysis
    waveform_preview: np.ndarray

    @property
    def duration_seconds(self) -> float:
        return self.playback_samples.shape[0] / float(self.analysis.sample_rate)

    @property
    def mono_samples(self) -> np.ndarray:
        return np.mean(self.playback_samples, axis=1, dtype=np.float32)


def _format_seconds(seconds: float) -> str:
    clamped = max(0.0, seconds)
    minutes = int(clamped // 60)
    remainder = clamped - (minutes * 60)
    return f"{minutes:02d}:{remainder:05.2f}"


def _nice_time_step(duration_seconds: float) -> float:
    if duration_seconds <= 15:
        return 1.0
    if duration_seconds <= 45:
        return 5.0
    if duration_seconds <= 180:
        return 15.0
    if duration_seconds <= 600:
        return 30.0
    return 60.0


def _discover_audio_paths(raw_inputs: list[str]) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    for raw_input in raw_inputs:
        candidate = Path(raw_input).expanduser().resolve()
        if not candidate.exists():
            continue
        if candidate.is_dir():
            matches = sorted(
                path for path in candidate.rglob("*") if path.suffix.lower() in AUDIO_SUFFIXES
            )
        elif candidate.suffix.lower() in AUDIO_SUFFIXES:
            matches = [candidate]
        else:
            matches = []
        for match in matches:
            if match in seen:
                continue
            seen.add(match)
            discovered.append(match)
    return discovered


def _expand_startup_paths(raw_inputs: list[str]) -> list[Path]:
    """Expand startup file arguments to include sibling songs.

    Passing a single song at launch should still populate the left sidebar with
    the full local set, which is more useful for comparison during exploration.
    """

    expanded_inputs: list[str] = []
    seen_inputs: set[str] = set()

    for raw_input in raw_inputs:
        candidate = Path(raw_input).expanduser().resolve()
        values = [str(candidate.parent)] if candidate.is_file() else [str(candidate)]
        for value in values:
            if value in seen_inputs:
                continue
            seen_inputs.add(value)
            expanded_inputs.append(value)

    return _discover_audio_paths(expanded_inputs)


def _decode_audio(path: Path, sample_rate: int, channels: int) -> np.ndarray:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError("ffmpeg is required but was not found on PATH")

    command = [
        ffmpeg_path,
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "pipe:1",
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        error_text = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(error_text or f"ffmpeg failed for {path}")
    decoded = np.frombuffer(result.stdout, dtype=np.float32)
    if decoded.size == 0:
        raise RuntimeError(f"Decoded audio from {path} is empty")
    return decoded.reshape(-1, channels).copy()


def _build_waveform_preview(samples: np.ndarray, bins: int = 4_096) -> np.ndarray:
    mono = np.mean(samples, axis=1, dtype=np.float32)
    if mono.size == 0:
        return np.zeros((0, 2), dtype=np.float32)
    chunk_size = max(1, int(np.ceil(mono.size / bins)))
    padded_length = chunk_size * bins
    if padded_length > mono.size:
        padded = np.pad(mono, (0, padded_length - mono.size))
    else:
        padded = mono
    reshaped = padded.reshape(-1, chunk_size)
    mins = reshaped.min(axis=1)
    maxes = reshaped.max(axis=1)
    return np.stack((mins, maxes), axis=1).astype(np.float32, copy=False)


class AudioPlayer:
    """Simple sample-buffer-backed transport built on sounddevice."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None
        self._sample_rate: int | None = None
        self._channels: int | None = None
        self._buffer: np.ndarray | None = None
        self._position_frames = 0
        self._playing = False
        self._paused = False

    def load(self, samples: np.ndarray, sample_rate: int) -> None:
        channels = int(samples.shape[1])
        with self._lock:
            self._buffer = samples
            self._position_frames = 0
            self._playing = False
            self._paused = False
        self._ensure_stream(sample_rate=sample_rate, channels=channels)

    def _ensure_stream(self, *, sample_rate: int, channels: int) -> None:
        if (
            self._stream is not None
            and self._sample_rate == sample_rate
            and self._channels == channels
        ):
            return

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

        self._sample_rate = sample_rate
        self._channels = channels
        self._stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            callback=self._callback,
            blocksize=1_024,
        )
        self._stream.start()

    def _callback(self, outdata: np.ndarray, frames: int, _time: object, _status: object) -> None:
        with self._lock:
            if self._buffer is None or not self._playing:
                outdata.fill(0.0)
                return

            end_frame = min(self._position_frames + frames, self._buffer.shape[0])
            chunk = self._buffer[self._position_frames:end_frame]
            outdata.fill(0.0)
            outdata[: chunk.shape[0], :] = chunk
            self._position_frames = end_frame

            if self._position_frames >= self._buffer.shape[0]:
                self._playing = False
                self._paused = False

    def play(self) -> None:
        with self._lock:
            if self._buffer is None:
                return
            self._playing = True
            self._paused = False

    def pause(self) -> None:
        with self._lock:
            if self._buffer is None:
                return
            self._playing = False
            self._paused = True

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._paused = False
            self._position_frames = 0

    def seek(self, seconds: float) -> None:
        with self._lock:
            if self._buffer is None or self._sample_rate is None:
                return
            target_frame = int(round(max(0.0, seconds) * self._sample_rate))
            self._position_frames = min(target_frame, self._buffer.shape[0] - 1)

    def current_time_seconds(self) -> float:
        with self._lock:
            if self._sample_rate is None:
                return 0.0
            return self._position_frames / float(self._sample_rate)

    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class TransientExplorerApp:
    def __init__(self, root: tk.Tk, config: ExplorerConfig) -> None:
        self._root = root
        self._config = config
        self._root.title("Transient Explorer")
        self._root.geometry("1400x860")
        self._root.configure(bg=_BACKGROUND_COLOR)

        self._player = AudioPlayer()
        self._paths: list[Path] = []
        self._track_cache: dict[Path, LoadedTrack] = {}
        self._current_track: LoadedTrack | None = None
        self._resize_after_id: str | None = None
        self._playhead_id: int | None = None
        self._visible_start_seconds = 0.0
        self._visible_duration_seconds = 0.0
        self._follow_playhead = True
        self._drag_pan_anchor_x: float | None = None
        self._drag_pan_start_seconds = 0.0

        self._status_var = tk.StringVar(value="Open one or more songs to begin.")
        self._transport_var = tk.StringVar(value="Stopped")
        self._selection_var = tk.StringVar(value="No track selected")
        self._transient_var = tk.StringVar(value="No transient data yet")
        self._view_var = tk.StringVar(value="View: full song")
        self._panel_mode_var = tk.StringVar(value="energy")

        self._build_ui()
        self._bind_shortcuts()
        self._schedule_transport_update()
        self._root.after(50, self._raise_window)

    def _build_ui(self) -> None:
        container = ttk.Frame(self._root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        sidebar = ttk.Frame(container)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Button(sidebar, text="Add Songs", command=self._open_files).pack(
            fill=tk.X
        )
        self._track_list = tk.Listbox(
            sidebar,
            width=36,
            activestyle="dotbox",
            exportselection=False,
            bg="#151b22",
            fg="#d7dde8",
            selectbackground="#28435a",
            selectforeground="#f8fbff",
            relief=tk.FLAT,
        )
        self._track_list.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._track_list.bind("<<ListboxSelect>>", self._on_track_selected)

        main = ttk.Frame(container)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        controls = ttk.Frame(main)
        controls.pack(fill=tk.X)
        ttk.Button(controls, text="Play / Pause", command=self._toggle_playback).pack(
            side=tk.LEFT
        )
        ttk.Button(controls, text="Stop", command=self._stop_playback).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        ttk.Button(
            controls,
            text="Prev Transient",
            command=lambda: self._jump_to_transient(direction=-1),
        ).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Button(
            controls,
            text="Next Transient",
            command=lambda: self._jump_to_transient(direction=1),
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Separator(controls, orient=tk.VERTICAL).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=12,
        )
        ttk.Button(
            controls,
            text="Zoom In",
            command=lambda: self._zoom_view(0.5),
        ).pack(side=tk.LEFT)
        ttk.Button(
            controls,
            text="Zoom Out",
            command=lambda: self._zoom_view(2.0),
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Pan Left",
            command=lambda: self._pan_view(-0.25),
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(
            controls,
            text="Pan Right",
            command=lambda: self._pan_view(0.25),
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            controls,
            text="Full View",
            command=self._reset_view,
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Separator(controls, orient=tk.VERTICAL).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=12,
        )
        ttk.Label(controls, text="Bottom").pack(side=tk.LEFT)
        panel_menu = ttk.OptionMenu(
            controls,
            self._panel_mode_var,
            self._panel_mode_var.get(),
            *PANEL_MODE_LABELS.keys(),
            command=lambda _value: self._render_canvas(),
        )
        panel_menu.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(main, textvariable=self._selection_var).pack(
            fill=tk.X,
            pady=(10, 0),
        )
        ttk.Label(main, textvariable=self._transport_var).pack(fill=tk.X, pady=(4, 0))
        ttk.Label(main, textvariable=self._transient_var).pack(fill=tk.X, pady=(4, 0))
        ttk.Label(main, textvariable=self._view_var).pack(fill=tk.X, pady=(4, 0))
        ttk.Label(main, textvariable=self._status_var).pack(fill=tk.X, pady=(4, 8))

        self._canvas = tk.Canvas(
            main,
            bg=_BACKGROUND_COLOR,
            highlightthickness=0,
            relief=tk.FLAT,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Button-1>", self._on_canvas_seek)
        self._canvas.bind("<B1-Motion>", self._on_canvas_seek)
        self._canvas.bind("<Shift-Button-1>", self._start_drag_pan)
        self._canvas.bind("<Shift-B1-Motion>", self._on_drag_pan)
        self._canvas.bind("<Shift-ButtonRelease-1>", self._end_drag_pan)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<MouseWheel>", self._on_mouse_wheel_pan)
        self._canvas.bind("<Control-MouseWheel>", self._on_mouse_wheel_zoom)
        self._canvas.bind("<Command-MouseWheel>", self._on_mouse_wheel_zoom)
        self._canvas.bind("<Button-4>", lambda _event: self._pan_view(-0.12))
        self._canvas.bind("<Button-5>", lambda _event: self._pan_view(0.12))
        self._canvas.bind(
            "<Control-Button-4>",
            lambda event: self._zoom_at_pointer(event, 0.8),
        )
        self._canvas.bind(
            "<Control-Button-5>",
            lambda event: self._zoom_at_pointer(event, 1.25),
        )

    def _bind_shortcuts(self) -> None:
        self._root.bind("<space>", lambda _event: self._toggle_playback())
        self._root.bind("<Left>", lambda _event: self._seek_by(-5.0))
        self._root.bind("<Right>", lambda _event: self._seek_by(5.0))
        self._root.bind("<Shift-Left>", lambda _event: self._seek_by(-30.0))
        self._root.bind("<Shift-Right>", lambda _event: self._seek_by(30.0))
        self._root.bind("-", lambda _event: self._zoom_view(1.5))
        self._root.bind("=", lambda _event: self._zoom_view(0.75))
        self._root.bind("_", lambda _event: self._zoom_view(1.5))
        self._root.bind("+", lambda _event: self._zoom_view(0.75))
        self._root.bind("a", lambda _event: self._pan_view(-0.2))
        self._root.bind("d", lambda _event: self._pan_view(0.2))
        self._root.bind("f", lambda _event: self._reset_view())
        self._root.bind("p", lambda _event: self._jump_to_transient(direction=-1))
        self._root.bind("n", lambda _event: self._jump_to_transient(direction=1))
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def add_paths(self, paths: list[Path]) -> None:
        added_any = False
        for path in paths:
            if path in self._paths:
                continue
            self._paths.append(path)
            self._track_list.insert(tk.END, path.name)
            added_any = True
        if added_any and self._current_track is None and self._paths:
            self._track_list.selection_clear(0, tk.END)
            self._track_list.selection_set(0)
            self._track_list.activate(0)
            self._load_track_by_index(0)
        if added_any:
            self._raise_window()

    def _open_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[
                ("Audio files", " ".join(f"*{suffix}" for suffix in sorted(AUDIO_SUFFIXES))),
                ("All files", "*.*"),
            ],
        )
        self.add_paths(_discover_audio_paths(list(selected)))
        self._raise_window()

    def _on_track_selected(self, _event: object) -> None:
        selection = self._track_list.curselection()
        if not selection:
            return
        self._load_track_by_index(int(selection[0]))

    def _load_track_by_index(self, index: int) -> None:
        path = self._paths[index]
        try:
            track = self._track_cache.get(path)
            if track is None:
                self._status_var.set(f"Decoding and analyzing {path.name}...")
                self._root.update_idletasks()
                playback_samples = _decode_audio(
                    path=path,
                    sample_rate=self._config.sample_rate,
                    channels=DEFAULT_CHANNELS,
                )
                analysis = analyze_transients(
                    np.mean(playback_samples, axis=1, dtype=np.float32),
                    self._config.sample_rate,
                    frame_size=self._config.frame_size,
                    hop_size=self._config.hop_size,
                    threshold_window_seconds=self._config.threshold_window_seconds,
                    threshold_scale=self._config.threshold_scale,
                    min_spacing_ms=self._config.min_spacing_ms,
                )
                track = LoadedTrack(
                    path=path,
                    playback_samples=playback_samples,
                    analysis=analysis,
                    waveform_preview=_build_waveform_preview(playback_samples),
                )
                self._track_cache[path] = track
        except Exception as exc:
            messagebox.showerror("Transient Explorer", f"Failed to load {path}:\n\n{exc}")
            self._status_var.set(f"Failed to load {path.name}")
            return

        self._current_track = track
        self._player.load(track.playback_samples, track.analysis.sample_rate)
        self._visible_start_seconds = 0.0
        self._visible_duration_seconds = track.duration_seconds
        self._follow_playhead = True
        self._selection_var.set(
            f"{track.path.name} | {_format_seconds(track.duration_seconds)} | "
            f"{len(track.analysis.transients)} transients | "
            f"range {track.analysis.band_low_hz:.0f}-{track.analysis.band_high_hz:.0f} Hz | "
            f"BPM {track.analysis.estimated_bpm:.0f}"
            if track.analysis.estimated_bpm is not None
            else f"{track.path.name} | {_format_seconds(track.duration_seconds)} | "
            f"{len(track.analysis.transients)} transients | "
            f"range {track.analysis.band_low_hz:.0f}-{track.analysis.band_high_hz:.0f} Hz"
        )
        self._status_var.set(
            "Click to seek. Two-finger scroll pans. "
            "Ctrl-scroll zooms. Shift-drag pans. A/D pans. F resets."
        )
        self._update_transient_label(track, 0.0)
        self._render_canvas()
        self._raise_window()

    def _render_canvas(self) -> None:
        self._canvas.delete("all")
        self._playhead_id = None
        track = self._current_track
        if track is None:
            return

        width = max(1, self._canvas.winfo_width())
        height = max(1, self._canvas.winfo_height())
        plot_left, plot_right = self._plot_bounds(width)

        waveform_top = 28
        waveform_bottom = int(height * 0.48)
        envelope_top = waveform_bottom + 36
        envelope_bottom = height - 32

        self._canvas.create_rectangle(0, 0, width, height, fill=_BACKGROUND_COLOR, outline="")
        self._canvas.create_text(
            16,
            12,
            text="Transient Timeline",
            anchor="w",
            fill="#9fb0c5",
        )
        self._canvas.create_text(
            16,
            waveform_bottom + 18,
            text=(
                f"{PANEL_MODE_LABELS[self._panel_mode_var.get()]} "
                f"({track.analysis.band_low_hz:.0f}-{track.analysis.band_high_hz:.0f} Hz)"
            ),
            anchor="w",
            fill="#9fb0c5",
        )

        visible_start, visible_end = self._visible_range(track)
        self._draw_time_grid(
            width=width,
            height=height,
            plot_left=plot_left,
            plot_right=plot_right,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )
        self._draw_bottom_panel_series(
            analysis=track.analysis,
            width=width,
            plot_left=plot_left,
            plot_right=plot_right,
            top=envelope_top,
            bottom=envelope_bottom,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )
        self._draw_transients(
            analysis=track.analysis,
            width=width,
            plot_left=plot_left,
            plot_right=plot_right,
            top=waveform_top,
            bottom=waveform_bottom,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )

        self._playhead_id = self._canvas.create_line(
            0,
            waveform_top,
            0,
            envelope_bottom,
            fill=_PLAYHEAD_COLOR,
            width=2,
        )
        self._update_playhead()

    def _visible_range(self, track: LoadedTrack) -> tuple[float, float]:
        duration = track.duration_seconds
        visible_duration = self._visible_duration_seconds or duration
        visible_duration = min(max(visible_duration, 1.0), duration)
        visible_start = min(max(self._visible_start_seconds, 0.0), max(duration - visible_duration, 0.0))
        visible_end = visible_start + visible_duration
        return visible_start, visible_end

    def _plot_bounds(self, width: int) -> tuple[int, int]:
        plot_left = _PLOT_LEFT_GUTTER
        plot_right = max(plot_left + 1, width - _PLOT_RIGHT_GUTTER)
        return plot_left, plot_right

    def _time_to_canvas_x(
        self,
        *,
        time_seconds: float,
        plot_left: int,
        plot_right: int,
        visible_start_seconds: float,
        visible_end_seconds: float,
    ) -> float:
        visible_duration = max(visible_end_seconds - visible_start_seconds, 0.001)
        plot_width = max(plot_right - plot_left, 1)
        return plot_left + (((time_seconds - visible_start_seconds) / visible_duration) * plot_width)

    def _canvas_x_to_time(
        self,
        *,
        x: float,
        plot_left: int,
        plot_right: int,
        visible_start_seconds: float,
        visible_end_seconds: float,
    ) -> float:
        plot_width = max(plot_right - plot_left, 1)
        fraction = min(max((x - plot_left) / plot_width, 0.0), 1.0)
        return visible_start_seconds + (fraction * (visible_end_seconds - visible_start_seconds))

    def _draw_time_grid(
        self,
        *,
        width: int,
        height: int,
        plot_left: int,
        plot_right: int,
        visible_start_seconds: float,
        visible_end_seconds: float,
    ) -> None:
        visible_duration = visible_end_seconds - visible_start_seconds
        step = _nice_time_step(visible_duration)
        t = step * int(visible_start_seconds // step)
        if t < visible_start_seconds:
            t += step
        while t <= visible_end_seconds + 0.001:
            x = int(round(self._time_to_canvas_x(
                time_seconds=t,
                plot_left=plot_left,
                plot_right=plot_right,
                visible_start_seconds=visible_start_seconds,
                visible_end_seconds=visible_end_seconds,
            )))
            self._canvas.create_line(x, 0, x, height, fill=_GRID_COLOR, width=1)
            self._canvas.create_text(
                min(x + 4, plot_right),
                height - 12,
                text=_format_seconds(t),
                anchor="sw",
                fill="#667187",
            )
            t += step

    def _draw_bottom_panel_scale(
        self,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
        peak_value: float,
    ) -> None:
        steps = 4
        drawable_height = max(1.0, bottom - top)
        self._canvas.create_line(left, top, left, bottom, fill=_GRID_COLOR, width=1)
        for index in range(steps + 1):
            fraction = index / steps
            y = bottom - (fraction * drawable_height)
            value = peak_value * fraction
            self._canvas.create_line(
                left,
                y,
                right,
                y,
                fill=_GRID_COLOR,
                width=1,
            )
            self._canvas.create_text(
                left - 8,
                y,
                text=f"{value:.2f}",
                anchor="e",
                fill="#7f8ca2",
            )

    def _series_for_panel_mode(self, analysis: TransientAnalysis) -> tuple[np.ndarray, str]:
        mode = self._panel_mode_var.get()
        if mode == "raw_flux":
            return analysis.raw_flux, _LOW_BAND_COLOR
        return analysis.low_band_energy, _LOW_BAND_COLOR

    def _draw_bottom_panel_series(
        self,
        *,
        analysis: TransientAnalysis,
        width: int,
        plot_left: int,
        plot_right: int,
        top: int,
        bottom: int,
        visible_start_seconds: float,
        visible_end_seconds: float,
    ) -> None:
        mode = self._panel_mode_var.get()
        series, color = self._series_for_panel_mode(analysis)
        show_threshold = mode == "energy"
        if series.size == 0 or (show_threshold and analysis.threshold.size == 0):
            return

        visible_mask = (
            (analysis.frame_times >= visible_start_seconds)
            & (analysis.frame_times <= visible_end_seconds)
        )
        if not np.any(visible_mask):
            return

        visible_times = analysis.frame_times[visible_mask]
        visible_values = series[visible_mask]
        visible_threshold = (
            analysis.threshold[visible_mask]
            if show_threshold
            else np.array([], dtype=np.float64)
        )
        peak_value = max(
            float(np.max(visible_values)),
            1e-9,
        )
        if show_threshold:
            peak_value = max(peak_value, float(np.max(visible_threshold)))
        self._draw_bottom_panel_scale(
            left=plot_left,
            right=plot_right,
            top=top,
            bottom=bottom,
            peak_value=peak_value,
        )
        panel_points: list[float] = []
        threshold_points: list[float] = []
        drawable_height = max(1.0, bottom - top)
        iterator = zip(visible_times, visible_values, strict=True)
        if show_threshold:
            iterator = zip(visible_times, visible_values, visible_threshold, strict=True)
        for items in iterator:
            if show_threshold:
                frame_time, value, threshold_value = items
            else:
                frame_time, value = items
            x = self._time_to_canvas_x(
                time_seconds=float(frame_time),
                plot_left=plot_left,
                plot_right=plot_right,
                visible_start_seconds=visible_start_seconds,
                visible_end_seconds=visible_end_seconds,
            )
            point_y = bottom - ((float(value) / peak_value) * drawable_height)
            panel_points.extend((x, point_y))
            if show_threshold:
                threshold_y = bottom - (
                    (float(threshold_value) / peak_value) * drawable_height
                )
                threshold_points.extend((x, threshold_y))
        self._canvas.create_line(
            panel_points,
            fill=color,
            width=2,
            smooth=False,
        )
        if show_threshold:
            self._canvas.create_line(
                threshold_points,
                fill=_SECONDARY_PANEL_COLOR,
                width=1,
                dash=(6, 4),
                smooth=False,
            )

    def _draw_transients(
        self,
        *,
        analysis: TransientAnalysis,
        width: int,
        plot_left: int,
        plot_right: int,
        top: int,
        bottom: int,
        visible_start_seconds: float,
        visible_end_seconds: float,
    ) -> None:
        for transient in analysis.transients:
            if (
                transient.time_seconds < visible_start_seconds
                or transient.time_seconds > visible_end_seconds
            ):
                continue
            x = int(round(self._time_to_canvas_x(
                time_seconds=transient.time_seconds,
                plot_left=plot_left,
                plot_right=plot_right,
                visible_start_seconds=visible_start_seconds,
                visible_end_seconds=visible_end_seconds,
            )))
            self._canvas.create_line(
                x,
                top,
                x,
                bottom,
                fill=_TRANSIENT_BASS_COLOR,
                width=1,
            )

    def _toggle_playback(self) -> None:
        if self._current_track is None:
            return
        if self._player.is_playing():
            self._player.pause()
        else:
            self._player.play()
            self._follow_playhead = True
        self._update_playhead()

    def _stop_playback(self) -> None:
        self._player.stop()
        self._follow_playhead = True
        self._update_playhead()

    def _seek_by(self, delta_seconds: float) -> None:
        if self._current_track is None:
            return
        position = self._player.current_time_seconds() + delta_seconds
        position = min(max(position, 0.0), self._current_track.duration_seconds)
        self._player.seek(position)
        self._follow_playhead = True
        self._ensure_time_visible(position)
        self._update_playhead()

    def _jump_to_transient(self, *, direction: int) -> None:
        track = self._current_track
        if track is None or not track.analysis.transients:
            return

        current = self._player.current_time_seconds()
        transient_times = np.array(
            [transient.time_seconds for transient in track.analysis.transients],
            dtype=np.float64,
        )
        if direction > 0:
            candidates = transient_times[transient_times > current + 0.01]
            if candidates.size == 0:
                target = float(transient_times[0])
            else:
                target = float(candidates[0])
        else:
            candidates = transient_times[transient_times < current - 0.01]
            if candidates.size == 0:
                target = float(transient_times[-1])
            else:
                target = float(candidates[-1])
        self._player.seek(target)
        self._follow_playhead = True
        self._ensure_time_visible(target)
        self._update_playhead()

    def _on_canvas_seek(self, event: tk.Event[tk.Misc]) -> None:
        track = self._current_track
        if track is None:
            return
        width = max(1, self._canvas.winfo_width())
        plot_left, plot_right = self._plot_bounds(width)
        visible_start, visible_end = self._visible_range(track)
        target_time = self._canvas_x_to_time(
            x=float(event.x),
            plot_left=plot_left,
            plot_right=plot_right,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )
        self._player.seek(target_time)
        self._follow_playhead = False
        self._update_playhead()

    def _on_mouse_wheel_pan(self, event: tk.Event[tk.Misc]) -> None:
        delta = float(getattr(event, "delta", 0.0))
        if delta == 0.0:
            return
        self._follow_playhead = False
        step = max(min(-(delta / 120.0) * 0.12, 0.45), -0.45)
        self._pan_view(step)

    def _on_mouse_wheel_zoom(self, event: tk.Event[tk.Misc]) -> None:
        delta = float(getattr(event, "delta", 0.0))
        if delta == 0.0:
            return
        if delta > 0:
            self._zoom_at_pointer(event, 0.8)
        else:
            self._zoom_at_pointer(event, 1.25)

    def _zoom_at_pointer(self, event: tk.Event[tk.Misc], factor: float) -> None:
        track = self._current_track
        if track is None:
            return
        self._follow_playhead = False
        width = max(1, self._canvas.winfo_width())
        plot_left, plot_right = self._plot_bounds(width)
        visible_start, visible_end = self._visible_range(track)
        anchor_time = self._canvas_x_to_time(
            x=float(getattr(event, "x", width / 2)),
            plot_left=plot_left,
            plot_right=plot_right,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )
        self._zoom_view(factor, anchor_time=anchor_time)

    def _zoom_view(self, factor: float, anchor_time: float | None = None) -> None:
        track = self._current_track
        if track is None:
            return
        self._follow_playhead = False
        visible_start, visible_end = self._visible_range(track)
        current_duration = visible_end - visible_start
        if anchor_time is None:
            anchor_time = visible_start + (current_duration / 2.0)
        target_duration = min(
            max(current_duration * factor, 1.0),
            track.duration_seconds,
        )
        if track.duration_seconds <= target_duration + 1e-6:
            self._visible_start_seconds = 0.0
            self._visible_duration_seconds = track.duration_seconds
            self._render_canvas()
            return
        anchor_fraction = 0.5
        if current_duration > 0:
            anchor_fraction = (anchor_time - visible_start) / current_duration
        anchor_fraction = min(max(anchor_fraction, 0.0), 1.0)
        new_start = anchor_time - (target_duration * anchor_fraction)
        new_start = min(max(new_start, 0.0), track.duration_seconds - target_duration)
        self._visible_start_seconds = new_start
        self._visible_duration_seconds = target_duration
        self._render_canvas()

    def _pan_view(self, fraction_of_window: float) -> None:
        track = self._current_track
        if track is None:
            return
        self._follow_playhead = False
        visible_start, visible_end = self._visible_range(track)
        visible_duration = visible_end - visible_start
        if track.duration_seconds <= visible_duration:
            return
        delta = visible_duration * fraction_of_window
        new_start = min(
            max(visible_start + delta, 0.0),
            track.duration_seconds - visible_duration,
        )
        self._visible_start_seconds = new_start
        self._visible_duration_seconds = visible_duration
        self._render_canvas()

    def _reset_view(self) -> None:
        track = self._current_track
        if track is None:
            return
        self._visible_start_seconds = 0.0
        self._visible_duration_seconds = track.duration_seconds
        self._follow_playhead = True
        self._render_canvas()

    def _start_drag_pan(self, event: tk.Event[tk.Misc]) -> str:
        track = self._current_track
        if track is None:
            return "break"
        self._follow_playhead = False
        self._drag_pan_anchor_x = float(event.x)
        self._drag_pan_start_seconds = self._visible_range(track)[0]
        return "break"

    def _on_drag_pan(self, event: tk.Event[tk.Misc]) -> str:
        track = self._current_track
        if track is None or self._drag_pan_anchor_x is None:
            return "break"
        visible_start, visible_end = self._visible_range(track)
        visible_duration = visible_end - visible_start
        plot_left, plot_right = self._plot_bounds(max(1, self._canvas.winfo_width()))
        plot_width = max(plot_right - plot_left, 1)
        delta_fraction = (float(event.x) - self._drag_pan_anchor_x) / plot_width
        new_start = self._drag_pan_start_seconds - (delta_fraction * visible_duration)
        new_start = min(
            max(new_start, 0.0),
            max(track.duration_seconds - visible_duration, 0.0),
        )
        self._visible_start_seconds = new_start
        self._visible_duration_seconds = visible_duration
        self._render_canvas()
        return "break"

    def _end_drag_pan(self, _event: tk.Event[tk.Misc]) -> str:
        self._drag_pan_anchor_x = None
        return "break"

    def _ensure_time_visible(self, time_seconds: float) -> None:
        track = self._current_track
        if track is None:
            return
        visible_start, visible_end = self._visible_range(track)
        if visible_start <= time_seconds <= visible_end:
            return
        visible_duration = visible_end - visible_start
        new_start = time_seconds - (visible_duration * 0.25)
        new_start = min(
            max(new_start, 0.0),
            max(track.duration_seconds - visible_duration, 0.0),
        )
        self._visible_start_seconds = new_start
        self._visible_duration_seconds = visible_duration
        self._render_canvas()

    def _on_canvas_resize(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is not None:
            self._root.after_cancel(self._resize_after_id)
        self._resize_after_id = self._root.after(75, self._render_canvas)

    def _schedule_transport_update(self) -> None:
        self._update_playhead()
        self._root.after(33, self._schedule_transport_update)

    def _update_playhead(self) -> None:
        track = self._current_track
        if track is None:
            self._transport_var.set("Stopped")
            self._view_var.set("View: full song")
            return

        current_time = min(self._player.current_time_seconds(), track.duration_seconds)
        width = max(1, self._canvas.winfo_width())
        if self._follow_playhead and (self._player.is_playing() or self._player.is_paused()):
            self._ensure_time_visible(current_time)
        visible_start, visible_end = self._visible_range(track)
        plot_left, plot_right = self._plot_bounds(width)
        x = int(round(self._time_to_canvas_x(
            time_seconds=current_time,
            plot_left=plot_left,
            plot_right=plot_right,
            visible_start_seconds=visible_start,
            visible_end_seconds=visible_end,
        )))

        if self._playhead_id is not None:
            coords = self._canvas.coords(self._playhead_id)
            if len(coords) == 4:
                self._canvas.coords(self._playhead_id, x, coords[1], x, coords[3])

        state = "Playing" if self._player.is_playing() else "Paused" if self._player.is_paused() else "Stopped"
        self._transport_var.set(
            f"{state} | {_format_seconds(current_time)} / {_format_seconds(track.duration_seconds)}"
        )
        self._view_var.set(
            f"View: {_format_seconds(visible_start)} - {_format_seconds(visible_end)} "
            f"({visible_end - visible_start:0.2f}s window)"
        )
        self._update_transient_label(track, current_time)

    def _update_transient_label(self, track: LoadedTrack, current_time: float) -> None:
        if not track.analysis.transients:
            self._transient_var.set("No transient markers detected for this file.")
            return

        nearest = min(
            track.analysis.transients,
            key=lambda transient: abs(transient.time_seconds - current_time),
        )
        self._transient_var.set(
            f"Nearest transient: {_format_seconds(nearest.time_seconds)} | "
            f"strength {nearest.strength:.3f} | "
            f"centroid {nearest.centroid_hz:.0f} Hz | "
            f"band-share {nearest.low_band_share:.2f} | "
            f"BPM {track.analysis.estimated_bpm:.0f} | "
            f"consistency {track.analysis.bpm_consistency:.2f}"
            if track.analysis.estimated_bpm is not None
            else f"Nearest transient: {_format_seconds(nearest.time_seconds)} | "
            f"strength {nearest.strength:.3f} | "
            f"centroid {nearest.centroid_hz:.0f} Hz | "
            f"band-share {nearest.low_band_share:.2f}"
        )

    def _on_close(self) -> None:
        self._player.close()
        self._root.destroy()

    def _raise_window(self) -> None:
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
            self._root.attributes("-topmost", True)
            self._root.after(250, lambda: self._root.attributes("-topmost", False))
        except tk.TclError:
            return


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactive transient explorer for local songs."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Audio files or directories to load on startup.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Decode and analysis sample rate.",
    )
    parser.add_argument(
        "--frame-size",
        type=int,
        default=DEFAULT_FRAME_SIZE,
        help="STFT frame size for the onset pass.",
    )
    parser.add_argument(
        "--hop-size",
        type=int,
        default=DEFAULT_HOP_SIZE,
        help="STFT hop size for the onset pass.",
    )
    parser.add_argument(
        "--threshold-window-seconds",
        type=float,
        default=DEFAULT_THRESHOLD_WINDOW_SECONDS,
        help="Bootstrap energy history window before enough peaks have been seen.",
    )
    parser.add_argument(
        "--threshold-scale",
        type=float,
        default=DEFAULT_THRESHOLD_SCALE,
        help="Fraction of the average of the last 3 accepted peaks.",
    )
    parser.add_argument(
        "--min-spacing-ms",
        type=float,
        default=DEFAULT_MIN_SPACING_MS,
        help="Minimum spacing between transient markers in milliseconds.",
    )
    return parser


def main() -> int:
    args = _build_argument_parser().parse_args()
    config = ExplorerConfig(
        sample_rate=args.sample_rate,
        frame_size=args.frame_size,
        hop_size=args.hop_size,
        threshold_window_seconds=args.threshold_window_seconds,
        threshold_scale=args.threshold_scale,
        min_spacing_ms=args.min_spacing_ms,
    )

    root = tk.Tk()
    app = TransientExplorerApp(root=root, config=config)
    startup_paths = _expand_startup_paths(args.paths)
    if startup_paths:
        app.add_paths(startup_paths)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
