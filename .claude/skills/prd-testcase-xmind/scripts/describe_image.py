#!/usr/bin/env python3
"""Describe an image via DeepSeek Anthropic-compatible vision API.

Usage:
  python3 describe_image.py <image_path> [--prompt "custom prompt"]

Output: text description of the image, tailored for test case analysis.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

DEFAULT_PROMPT = (
    "请详细描述这张图片的内容。如果是UI设计稿或原型图，请列出："
    "1) 页面布局结构 2) 所有可见的按钮、文字、图标 3) 列表或表格的排序规则 "
    "4) 不同状态下的展示差异（如置灰、高亮） 5) 弹窗或提示文案。"
    "如果是流程图，请描述完整的状态路径、分支条件和异常分支。"
    "如果是表格截图，请逐行列出字段名和枚举值。"
)


def get_api_config() -> tuple[str, str, str]:
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
    model = os.environ.get("ANTHROPIC_MODEL", "Deepseek-v4-pro[1m]")
    if not api_key:
        print("Error: ANTHROPIC_AUTH_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    return api_key, base_url.rstrip("/"), model


def image_to_base64(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    media_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/png")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode(), media_type


def call_vision_api(api_key: str, base_url: str, model: str, img_b64: str, media_type: str, prompt: str) -> str:
    payload = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        f"{base_url}/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        body = json.loads(resp.read().decode())
        for c in body.get("content", []):
            if c.get("type") == "text":
                return c["text"]
        return json.dumps(body, ensure_ascii=False)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500]
        print(f"API error HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Describe an image via DeepSeek vision API for test case analysis.")
    parser.add_argument("image", type=Path, help="Path to the image file (PNG/JPG/GIF/WebP).")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT, help="Custom description prompt.")
    args = parser.parse_args(argv)

    if not args.image.exists():
        print(f"Error: file not found: {args.image}", file=sys.stderr)
        return 1

    api_key, base_url, model = get_api_config()
    img_b64, media_type = image_to_base64(args.image)
    description = call_vision_api(api_key, base_url, model, img_b64, media_type, args.prompt)
    print(description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
