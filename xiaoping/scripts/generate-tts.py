#!/usr/bin/env python3
"""Generate TTS audio with word-level timestamps for Remotion subtitle sync."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import edge_tts

# Default voice for Chinese narration
DEFAULT_VOICE = "zh-CN-YunyangNeural"

# Rate adjustment: positive = faster, negative = slower
DEFAULT_RATE = "+0%"


async def generate_tts(text: str, voice: str, rate: str, output_dir: str) -> dict:
    """Generate TTS audio and return metadata with word timestamps."""
    os.makedirs(output_dir, exist_ok=True)

    audio_path = os.path.join(output_dir, "narration.mp3")
    metadata_path = os.path.join(output_dir, "metadata.json")

    communicate = edge_tts.Communicate(text, voice, rate=rate)

    # Collect word boundaries
    word_boundaries = []

    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"] / 10_000_000,  # Convert to seconds
                    "duration": chunk["duration"] / 10_000_000,
                })

    # Build subtitle segments by splitting on punctuation
    segments = build_segments(word_boundaries, text)

    metadata = {
        "audio_file": "narration.mp3",
        "voice": voice,
        "rate": rate,
        "segments": segments,
        "total_words": len(word_boundaries),
        "total_duration": word_boundaries[-1]["offset"] + word_boundaries[-1]["duration"] if word_boundaries else 0,
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Generated: {audio_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Segments: {len(segments)}")
    print(f"Duration: {metadata['total_duration']:.1f}s")

    return metadata


def build_segments(word_boundaries: list, original_text: str) -> list:
    """Build subtitle segments from word boundaries.

    Groups words into segments based on punctuation in the original text.
    Each segment is a subtitle line that will be displayed together.
    """
    if not word_boundaries:
        return []

    # Split original text into sentences by punctuation
    import re
    # Split on Chinese/English sentence endings
    sentences = re.split(r'([。！？!?\n])', original_text)
    # Rebuild sentences with their delimiters
    rebuilt = []
    i = 0
    while i < len(sentences):
        s = sentences[i]
        if i + 1 < len(sentences) and sentences[i + 1] in '。！？!?\n':
            s += sentences[i + 1]
            i += 2
        else:
            i += 1
        s = s.strip()
        if s:
            rebuilt.append(s)

    # Now match word boundaries to sentences
    segments = []
    word_idx = 0

    for sentence in rebuilt:
        # Find words that belong to this sentence
        sentence_words = []
        sentence_text = sentence.replace('\n', '').strip()

        # Collect words until we've covered enough characters
        chars_needed = len(sentence_text)
        chars_collected = 0

        while word_idx < len(word_boundaries) and chars_collected < chars_needed:
            w = word_boundaries[word_idx]
            sentence_words.append(w)
            chars_collected += len(w["text"])
            word_idx += 1

        if sentence_words:
            start_time = sentence_words[0]["offset"]
            end_time = sentence_words[-1]["offset"] + sentence_words[-1]["duration"]

            # Use original sentence text (preserve punctuation)
            display_text = sentence_text

            segments.append({
                "text": display_text,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "duration": round(end_time - start_time, 3),
            })

    return segments


async def main():
    if len(sys.argv) < 2:
        print("Usage: generate-tts.py <text_or_file> [output_dir] [voice] [rate]")
        print("  text_or_file: text string or path to .txt file")
        print("  output_dir: output directory (default: ./tts-output)")
        print("  voice: TTS voice (default: zh-CN-YunyangNeural)")
        print("  rate: speech rate (default: +0%)")
        sys.exit(1)

    text_input = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./tts-output"
    voice = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VOICE
    rate = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_RATE

    # Read text from file if it's a file path
    if os.path.isfile(text_input):
        with open(text_input, "r", encoding="utf-8") as f:
            text = f.read().strip()
    else:
        text = text_input

    if not text:
        print("Error: empty text")
        sys.exit(1)

    await generate_tts(text, voice, rate, output_dir)


if __name__ == "__main__":
    asyncio.run(main())
