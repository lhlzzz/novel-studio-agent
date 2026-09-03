#!/usr/bin/env python3
"""Contract reference for XiaoleAI OpenAI-compatible image generation.

Production execution owner is `creative.providers.lechuang.LechuangAdapter`.
This script remains the documented request/response contract. Do not use it as
a second production media pipeline.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "https://api.xiaoleai.team/v1"
SUPPORTED_MODELS = {
    "gpt-image-2",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
}
SUPPORTED_SIZES = {"512", "1K", "2K", "4K"}
ENDPOINTS = {
    "generations": "/images/generations",
    "created": "/image/created",
}
PLATFORM_DEFAULTS = {
    "xiaohongshu": {"aspect_ratio": "3:4", "output_dir": "xiaohongshu"},
    "kuaishou": {"aspect_ratio": "9:16", "output_dir": "kuaishou"},
    "douyin": {"aspect_ratio": "9:16", "output_dir": "douyin"},
    "x": {"aspect_ratio": "16:9", "output_dir": "x"},
    "shipinghao": {"aspect_ratio": "9:16", "output_dir": "shipinghao"},
    "xianyu": {"aspect_ratio": "1:1", "output_dir": "xianyu"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Image generation prompt.")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 file containing the prompt.")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        help="Output path prefix; _1, _2, ... and the image suffix are appended.",
    )
    parser.add_argument(
        "--platform",
        choices=sorted(PLATFORM_DEFAULTS),
        help="Platform workspace requesting the asset; selects a default ratio and shared output directory.",
    )
    parser.add_argument(
        "--asset-name",
        default="image",
        help="Filename stem used when --output-prefix is omitted.",
    )
    parser.add_argument("--model", default="gpt-image-2", choices=sorted(SUPPORTED_MODELS))
    parser.add_argument("--image-size", default="2K", choices=sorted(SUPPORTED_SIZES))
    parser.add_argument("--aspect-ratio", default=None)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument(
        "--endpoint",
        default="generations",
        choices=sorted(ENDPOINTS),
        help="Use the standard generations endpoint or the alternate created endpoint.",
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def get_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        prompt = args.prompt
    else:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"无法读取 prompt 文件: {args.prompt_file}: {exc}") from exc
    prompt = prompt.strip()
    if not prompt:
        raise RuntimeError("prompt 不能为空")
    return prompt


def parse_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        for key in ("message", "detail"):
            if payload.get(key):
                return str(payload[key])
    return response.text.strip() or f"HTTP {response.status_code}"


def decode_image(value: Any) -> tuple[bytes, str]:
    raw = str(value or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = "".join(raw.split())
    try:
        image_bytes = base64.b64decode(raw + "=" * ((4 - len(raw) % 4) % 4), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("响应中的 b64_json 不是有效 Base64") from exc

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return image_bytes, ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return image_bytes, ".jpg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return image_bytes, ".gif"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return image_bytes, ".webp"
    raise RuntimeError("响应中的 b64_json 不是受支持的 PNG/JPEG/GIF/WEBP 图片")


def save_items(items: list[Any], prefix: Path, overwrite: bool) -> list[str]:
    saved: list[str] = []
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not item.get("b64_json"):
            raise RuntimeError(f"data[{index - 1}] 缺少 b64_json")
        image_bytes, suffix = decode_image(item["b64_json"])
        output = prefix.parent / f"{prefix.name}_{index}{suffix}"
        if output.exists() and not overwrite:
            raise RuntimeError(f"输出文件已存在，使用 --overwrite 才能覆盖: {output}")
        output.write_bytes(image_bytes)
        saved.append(str(output))
    return saved


def main() -> int:
    args = parse_args()
    if args.n < 1 or args.n > 4:
        raise RuntimeError("--n 必须在 1 到 4 之间")
    if args.model != "gpt-image-2" and args.n != 1:
        raise RuntimeError("当前非 gpt-image-2 模型只支持 --n 1")

    if args.output_prefix is None and args.platform is None:
        raise RuntimeError("必须提供 --output-prefix，或同时提供 --platform 让共享 owner 选择平台输出目录")

    if args.platform:
        platform_defaults = PLATFORM_DEFAULTS[args.platform]
        if args.aspect_ratio is None:
            args.aspect_ratio = platform_defaults["aspect_ratio"]
        if args.output_prefix is None:
            project_root = Path(__file__).resolve().parents[5]
            args.output_prefix = (
                project_root
                / "videos"
                / "generated-frames"
                / platform_defaults["output_dir"]
                / args.asset_name
            )
    elif args.aspect_ratio is None:
        args.aspect_ratio = "9:16"

    api_key = os.environ.get("XIAOLEAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未配置 XiaoleAI API key")

    payload = {
        "model": args.model,
        "prompt": get_prompt(args),
        "response_format": "b64_json",
        "image_size": args.image_size,
        "aspect_ratio": args.aspect_ratio,
        "n": args.n,
    }
    base_url = os.environ.get("XIAOLEAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}{ENDPOINTS[args.endpoint]}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=args.timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"图片接口请求失败: {exc}") from exc
    if not response.ok:
        raise RuntimeError(f"图片生成失败 HTTP {response.status_code}: {parse_error(response)}")

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("图片接口返回了无效 JSON") from exc
    items = result.get("data") if isinstance(result, dict) else None
    if not isinstance(items, list) or not items:
        raise RuntimeError("图片生成成功但 data 为空")

    saved = save_items(items, args.output_prefix, args.overwrite)
    summary = {
        "saved": saved,
        "platform": args.platform,
        "model": result.get("model", args.model),
        "request_id": result.get("request_id"),
        "usage": result.get("usage", {}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
