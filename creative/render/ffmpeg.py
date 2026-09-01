"""ffmpeg/ffprobe owner. Failures raise TechnicalMediaError, never fake files."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from creative.errors import TechnicalMediaError

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run_ffmpeg(args: list[str], *, timeout: int = 120) -> None:
    command = [FFMPEG, "-y", *args]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise TechnicalMediaError("ffmpeg is not installed", details={"args": args}) from exc
    except subprocess.TimeoutExpired as exc:
        raise TechnicalMediaError("ffmpeg timed out", details={"args": args}) from exc
    if proc.returncode != 0:
        raise TechnicalMediaError(
            (proc.stderr or proc.stdout or "ffmpeg failed").strip()[:2000],
            details={"args": args, "returncode": proc.returncode},
        )


def probe(path: str | Path) -> dict[str, Any]:
    target = str(path)
    command = [
        FFPROBE, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", target,
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        raise TechnicalMediaError("ffprobe is not installed", details={"path": target}) from exc
    if proc.returncode != 0:
        raise TechnicalMediaError(
            (proc.stderr or "ffprobe failed").strip()[:2000],
            details={"path": target},
        )
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise TechnicalMediaError("ffprobe returned invalid json", details={"path": target}) from exc


def video_info(path: str | Path) -> dict[str, Any]:
    data = probe(path)
    streams = data.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None) or {}
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    fmt = data.get("format") or {}
    fps_raw = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    fps = 0.0
    if "/" in fps_raw:
        num, den = fps_raw.split("/", 1)
        if float(den or 0):
            fps = float(num) / float(den)
    elif fps_raw:
        fps = float(fps_raw)
    return {
        "codec": str(video.get("codec_name") or ""),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "duration": float(fmt.get("duration") or video.get("duration") or 0),
        "audio": bool(audio),
        "filesize": int(fmt.get("size") or Path(path).stat().st_size),
        "mime": "video/mp4",
    }


def extract_frames(path: str | Path, dest_dir: str | Path, positions: list[float] | None = None) -> list[str]:
    info = video_info(path)
    duration = max(float(info.get("duration") or 0), 0.1)
    marks = positions or [0.0, duration * 0.25, duration * 0.5, duration * 0.75, max(duration - 0.05, 0.0)]
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, ts in enumerate(marks):
        out = dest / f"frame-{index:02d}.png"
        run_ffmpeg(["-ss", f"{max(ts, 0):.3f}", "-i", str(path), "-frames:v", "1", str(out)])
        if out.exists() and out.stat().st_size > 0:
            frames.append(str(out))
    if not frames:
        raise TechnicalMediaError("failed to extract video frames", details={"path": str(path)})
    return frames


def write_srt(path: Path, text: str, duration: float) -> Path:
    path.write_text(f"1\n00:00:00,000 --> {_srt_ts(duration)}\n{text}\n", encoding="utf-8")
    return path


def write_ass(path: Path, text: str, duration: float) -> Path:
    end = _ass_ts(duration)
    body = (
        "[Script Info]\nScriptType: v4.00+\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,20,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        f"Dialogue: 0,0:00:00.00,{end},Default,,0,0,0,,{text}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _srt_ts(seconds: float) -> str:
    total = max(int(seconds * 1000), 1)
    hours, rem = divmod(total, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _ass_ts(seconds: float) -> str:
    total = max(seconds, 0.04)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"
