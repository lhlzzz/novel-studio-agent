"""Execute a render plan into a new hashed MediaAsset."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from creative.assets import persist_file
from creative.errors import TechnicalMediaError
from creative.render.ffmpeg import run_ffmpeg, video_info, write_ass, write_srt
from creative.render.schemas import RenderOp, RenderPlan
from creative.schemas import MediaAsset


def render_asset(
    source: MediaAsset,
    *,
    store,
    ops: list[RenderOp] | None = None,
    extra: dict[str, Any] | None = None,
) -> MediaAsset:
    plan = RenderPlan(inputs=(source.path,), ops=tuple(ops or (RenderOp("export"),)))
    return execute_plan(plan, source=source, store=store, extra=extra or {})


def execute_plan(plan: RenderPlan, *, source: MediaAsset, store, extra: dict[str, Any] | None = None) -> MediaAsset:
    extra = extra or {}
    src = Path(source.path)
    if not src.exists():
        raise TechnicalMediaError(f"render input missing: {src}")
    with tempfile.TemporaryDirectory(prefix="meiti-render-") as tmp:
        work = Path(tmp)
        current = src
        current_kind = "image" if source.type in {"image", "reference"} and source.mime_type.startswith("image/") else source.type
        for op in plan.ops or (RenderOp("export"),):
            current, current_kind = _apply(op, current, current_kind, work, source)
        suffix = current.suffix or (".png" if current_kind == "image" else ".mp4")
        asset_type = "final" if current_kind in {"video", "final"} else current_kind
        fields = {
            "workflow_id": extra.get("workflow_id") or source.workflow_id,
            "workflow_version": extra.get("workflow_version") or source.workflow_version,
            "creative_run_id": extra.get("creative_run_id") or source.creative_run_id,
            "character_id": extra.get("character_id") or source.character_id,
            "metadata": {**dict(source.metadata or {}), "rendered_from": source.asset_id, "ops": [item.op for item in plan.ops]},
        }
        if current_kind == "image":
            from PIL import Image
            with Image.open(current) as image:
                width, height = image.size
            asset = persist_file(current, asset_type="image" if asset_type != "final" else "final", root=store.assets.root, mime_type="image/png", width=width, height=height, **fields)
        else:
            info = video_info(current)
            asset = persist_file(
                current,
                asset_type="final" if source.type in {"video", "final"} else source.type,
                root=store.assets.root,
                mime_type="video/mp4",
                width=info["width"],
                height=info["height"],
                duration=info["duration"],
                fps=info["fps"],
                **fields,
            )
        return store.assets.put(asset)


def _apply(op: RenderOp, current: Path, kind: str, work: Path, source: MediaAsset) -> tuple[Path, str]:
    name = op.op
    params = dict(op.params or {})
    out = work / f"{name}-{current.stem}{current.suffix if kind != 'image' else '.mp4' if name in {'export', 'concat', 'trim'} and kind != 'image' else current.suffix}"
    if name == "trim":
        start = str(params.get("start") or 0)
        duration = str(params.get("duration") or source.duration or 1)
        run_ffmpeg(["-ss", start, "-i", str(current), "-t", duration, "-c", "copy", str(out)])
        return out, "video"
    if name == "concat":
        files = [str(current), *[str(item) for item in params.get("others") or []]]
        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{item}'\n" for item in files), encoding="utf-8")
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
        return out, "video"
    if name == "resize":
        width = int(params.get("width") or source.width or 720)
        height = int(params.get("height") or source.height or 1280)
        if kind == "image":
            from PIL import Image
            with Image.open(current) as image:
                image.resize((width, height)).save(out)
            return out, "image"
        run_ffmpeg(["-i", str(current), "-vf", f"scale={width}:{height}", str(out)])
        return out, "video"
    if name == "fps":
        fps = str(params.get("fps") or source.fps or 24)
        run_ffmpeg(["-i", str(current), "-r", fps, str(out)])
        return out, "video"
    if name == "mute":
        run_ffmpeg(["-i", str(current), "-an", str(out)])
        return out, "video"
    if name == "audio":
        audio = params.get("audio")
        if not audio:
            raise TechnicalMediaError("audio mix requires an audio file")
        run_ffmpeg(["-i", str(current), "-i", str(audio), "-c:v", "copy", "-shortest", str(out)])
        return out, "video"
    if name == "subtitle":
        text = str(params.get("text") or params.get("instruction") or "")
        duration = float(params.get("duration") or source.duration or 3)
        mode = str(params.get("format") or "burn-in")
        if mode == "srt":
            srt = write_srt(work / "subs.srt", text, duration)
            return srt, "subtitle"
        if mode == "ass":
            ass = write_ass(work / "subs.ass", text, duration)
            return ass, "subtitle"
        srt = write_srt(work / "subs.srt", text, duration)
        run_ffmpeg(["-i", str(current), "-vf", f"subtitles={srt}", str(out)])
        return out, "video"
    if name in {"merge", "export"}:
        if kind == "image":
            from PIL import Image
            out = work / f"export-{current.stem}.png"
            with Image.open(current) as image:
                image.convert("RGB").save(out, format="PNG")
            return out, "image"
        out = work / f"export-{current.stem}.mp4"
        run_ffmpeg(["-i", str(current), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)])
        return out, "video"
    raise TechnicalMediaError(f"unknown render op: {name}")
