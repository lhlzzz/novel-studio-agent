#!/usr/bin/env python3
"""Generate TTS audio + SRT subtitles + Remotion props for publishable videos."""

import asyncio
import json
import os
import re
import sys
import shutil
from pathlib import Path

sys.path.insert(0, '/root/hermes/company-ai-system/tools/external/venvs/edge-tts')
import edge_tts

DEFAULT_VOICE = "zh-CN-YunyangNeural"


def srt_to_seconds(srt_time: str) -> float:
    """Convert SRT time format 'HH:MM:SS,mmm' to seconds."""
    parts = srt_time.replace(',', '.').split(':')
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def parse_srt(srt_text: str) -> list:
    """Parse SRT text into segment list."""
    blocks = srt_text.strip().split('\n\n')
    segments = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_line = lines[1]
            text = ' '.join(lines[2:])
            match = re.match(r'(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)', time_line)
            if match:
                start = srt_to_seconds(match.group(1))
                end = srt_to_seconds(match.group(2))
                segments.append({
                    "text": text.strip(),
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3),
                })
    return segments


async def generate_tts(text: str, voice: str, rate: str, output_dir: str) -> dict:
    """Generate TTS audio and SRT subtitles."""
    os.makedirs(output_dir, exist_ok=True)

    audio_path = os.path.join(output_dir, "narration.mp3")
    srt_path = os.path.join(output_dir, "subtitles.srt")

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    submaker = edge_tts.SubMaker()

    audio_data = b''
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            audio_data += chunk['data']
        elif chunk['type'] == 'SentenceBoundary':
            submaker.feed(chunk)

    with open(audio_path, "wb") as f:
        f.write(audio_data)

    srt_content = submaker.get_srt()
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    segments = parse_srt(srt_content)
    total_duration = segments[-1]["end"] if segments else 0

    metadata = {
        "audio_file": "narration.mp3",
        "srt_file": "subtitles.srt",
        "voice": voice,
        "rate": rate,
        "segments": segments,
        "total_segments": len(segments),
        "total_duration": round(total_duration, 1),
    }

    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


async def main():
    if len(sys.argv) < 2:
        print("Usage: build-video.py <project.json>")
        sys.exit(1)

    project_file = sys.argv[1]
    with open(project_file, "r", encoding="utf-8") as f:
        project = json.load(f)

    title = project["title"]
    subtitle = project.get("subtitle", "")
    narration = project["narration"]
    accent_color = project.get("accentColor", "#38bdf8")
    voice = project.get("voice", DEFAULT_VOICE)
    rate = project.get("rate", "+0%")

    project_name = Path(project_file).stem
    output_dir = f"/root/hermes/company-ai-system/workspaces/xiaoping/videos/tts-output/{project_name}"
    static_dir = "/root/hermes/company-ai-system/workspaces/xiaoping/public"

    print(f"Project: {title}")
    print(f"Output: {output_dir}")

    # Generate TTS
    print("\n[1/3] Generating TTS audio + subtitles...")
    metadata = await generate_tts(narration, voice, rate, output_dir)
    print(f"  Duration: {metadata['total_duration']}s")
    print(f"  Segments: {metadata['total_segments']}")

    # Copy assets to Remotion public dir
    print("\n[2/3] Copying assets to Remotion public/...")
    remotion_public = "/root/hermes/company-ai-system/workspaces/xiaoping/videos/low-pressure-start/public"
    os.makedirs(remotion_public, exist_ok=True)
    shutil.copy2(os.path.join(output_dir, "narration.mp3"), os.path.join(remotion_public, "narration.mp3"))
    bgm_src = "/root/hermes/company-ai-system/tools/external/repos/Pixelle-Video/bgm/default.mp3"
    if os.path.exists(bgm_src):
        shutil.copy2(bgm_src, os.path.join(remotion_public, "bgm.mp3"))
        print("  BGM: bgm.mp3")
    print("  Audio: narration.mp3")

    # Generate Remotion props
    print("\n[3/3] Generating Remotion props...")
    props = {
        "title": title,
        "subtitle": subtitle,
        "segments": metadata["segments"],
        "audioFile": "narration.mp3",
        "bgmFile": "bgm.mp3",
        "bgmVolume": 0.12,
        "accentColor": accent_color,
    }

    props_path = os.path.join(output_dir, "props.json")
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
    print(f"  Props: {props_path}")

    # Print render instructions
    print(f"\n{'='*60}")
    print(f"READY TO RENDER")
    print(f"{'='*60}")
    
    render_output = f"/root/hermes/company-ai-system/workspaces/xiaoping/videos/publish-ready/{project_name}.mp4"
    public_dir = "/root/hermes/company-ai-system/workspaces/xiaoping/videos/low-pressure-start/public"
    entry_point = "/root/hermes/company-ai-system/workspaces/xiaoping/videos/low-pressure-start/index.ts"
    
    print(f"\nRender command:")
    print(f"  /root/hermes/company-ai-system/tools/external/bin/node-tool remotion render \\")
    print(f"    {entry_point} TtsNarration \\")
    print(f"    --public-dir={public_dir} \\")
    print(f"    --props={props_path} \\")
    print(f"    --output={render_output}")
    
    print(f"\nAfter render, trim to actual duration:")
    print(f"  ffmpeg -i {render_output} -t {metadata['total_duration']:.1f} -c copy {render_output}.trimmed.mp4 && mv {render_output}.trimmed.mp4 {render_output}")
    print(f"\nSubtitle preview:")
    for i, seg in enumerate(metadata["segments"]):
        print(f"  [{seg['start']:5.1f}s - {seg['end']:5.1f}s] {seg['text']}")


if __name__ == "__main__":
    asyncio.run(main())
