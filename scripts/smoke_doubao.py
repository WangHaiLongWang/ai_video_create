"""Controlled Doubao Seedream/Seedance smoke test (real API, potentially billable)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings
from backend.app.providers.doubao_provider import DoubaoProvider


async def run(mode: str, image_path: Path, video_path: Path) -> None:
    settings = Settings()
    provider = DoubaoProvider(
        settings.DOUBAO_API_KEY,
        settings.DOUBAO_API_URL,
        settings.DOUBAO_IMAGE_MODEL,
        settings.DOUBAO_VIDEO_MODEL,
        {
            "size": settings.DOUBAO_IMAGE_SIZE,
            "resolution": settings.DOUBAO_VIDEO_RESOLUTION,
            "ratio": settings.DOUBAO_VIDEO_RATIO,
            "duration": settings.DOUBAO_VIDEO_DURATION,
            "seed": settings.DOUBAO_SEED,
            "watermark": settings.DOUBAO_WATERMARK,
            "camera_fixed": settings.DOUBAO_CAMERA_FIXED,
            "poll_interval": settings.DOUBAO_POLL_INTERVAL,
            "timeout": settings.DOUBAO_TIMEOUT,
        },
    )
    try:
        if mode == "health":
            print(json.dumps({"health": await provider.health_check()}))
            return
        if mode == "models":
            response = await (await provider._get_client()).get("/models")
            response.raise_for_status()
            models = response.json().get("data") or []
            print(json.dumps({
                "models": [
                    {"id": item.get("id"), "owned_by": item.get("owned_by")}
                    for item in models
                ]
            }, ensure_ascii=False))
            return

        image_path.parent.mkdir(parents=True, exist_ok=True)
        if mode in {"image", "all"}:
            started = time.time()
            data = await provider.generate_image(
                "写实电影感冬季滑雪教学场景，晴朗白天，初级雪道，一位单板教练指导一位初学者，中景低机位，35mm镜头，自然光，超写实，高细节，背景无其他人",
            )
            image_path.write_bytes(data)
            print(json.dumps({
                "stage": "image",
                "ok": True,
                "path": str(image_path),
                "bytes": len(data),
                "seconds": round(time.time() - started, 2),
                "model": settings.DOUBAO_IMAGE_MODEL,
            }, ensure_ascii=False))

        if mode in {"video", "all"}:
            if mode == "all" and not image_path.is_file():
                raise RuntimeError(f"Input image not found: {image_path}")
            video_path.parent.mkdir(parents=True, exist_ok=True)
            started = time.time()
            data = await provider.generate_video(
                str(image_path) if image_path.is_file() else "",
                "教练缓慢指向学员前脚固定器，学员轻微屈膝准备蹬行，镜头稳定缓慢前推，雪粒自然飞溅，人物数量保持为两人",
            )
            video_path.write_bytes(data)
            print(json.dumps({
                "stage": "video",
                "ok": True,
                "path": str(video_path),
                "bytes": len(data),
                "seconds": round(time.time() - started, 2),
                "model": settings.DOUBAO_VIDEO_MODEL,
                "external_job_id": provider.get_external_job_id(),
            }, ensure_ascii=False))
    finally:
        await provider.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["health", "models", "image", "video", "all"])
    parser.add_argument("--image", type=Path, default=Path("data/assets/doubao-uat/seedream-ski.png"))
    parser.add_argument("--video", type=Path, default=Path("data/assets/doubao-uat/seedance-ski.mp4"))
    args = parser.parse_args()
    asyncio.run(run(args.mode, args.image, args.video))


if __name__ == "__main__":
    main()
