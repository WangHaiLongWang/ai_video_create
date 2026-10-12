"""MiMo -> Qwen Image -> Wan3 minimal real-chain smoke (real API, billable).

Usage:
    python scripts/smoke_real_chain.py health     # 只做健康探测，最便宜
    python scripts/smoke_real_chain.py models     # 列出可见模型
    python scripts/smoke_real_chain.py chain      # 最小真实链路：1 scene / 1 image / 1 short video

设计原则（对齐 PLATFORM-HARDENING HARD-503/504）：
- 调用量上限：chain 模式最多 1 次文本、1 次生图、1 次生视频。
- 产物落盘到 data/uat/，带时间戳，便于清理。
- 绝不打印 API Key；只打印健康结果、模型 ID、耗时、产物路径与文件大小。
"""

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

from backend.app.config import Settings  # noqa: E402


def _out(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


async def _build_providers(settings: Settings):
    from backend.app.providers.openai_compat_provider import OpenAICompatProvider
    from backend.app.providers.dashscope_provider import DashScopeProvider
    from backend.app.providers.wan3_provider import Wan3VideoProvider

    # MiMo 当前上限 131072 completion tokens；.env 若配得更大（如 1048576）会直接 400。
    # 这里钳位到 8192，保证 smoke 可跑；根治需修正 .env 或在 Provider 侧校验（见报告）。
    safe_max_tokens = max(1, min(int(settings.OPENAI_COMPAT_MAX_TOKENS or 4096), 8192))
    mimo = OpenAICompatProvider(
        settings.OPENAI_COMPAT_API_KEY,
        settings.OPENAI_COMPAT_API_URL,
        settings.OPENAI_COMPAT_MODEL,
        display_name=settings.OPENAI_COMPAT_NAME,
        auth_header=settings.OPENAI_COMPAT_AUTH_HEADER,
        auth_scheme=settings.OPENAI_COMPAT_AUTH_SCHEME,
        max_tokens_param=settings.OPENAI_COMPAT_MAX_TOKENS_PARAM,
        default_config={
            "max_tokens": safe_max_tokens,
            "temperature": settings.OPENAI_COMPAT_TEMPERATURE,
            "top_p": settings.OPENAI_COMPAT_TOP_P,
            "timeout": settings.OPENAI_COMPAT_TIMEOUT,
        },
    )
    qwen = DashScopeProvider(
        settings.DASHSCOPE_API_KEY,
        settings.DASHSCOPE_API_URL,
        settings.DASHSCOPE_IMAGE_MODEL,
        {
            "size": settings.DASHSCOPE_IMAGE_SIZE,
            "use_async": settings.DASHSCOPE_USE_ASYNC,
            "prompt_extend": settings.DASHSCOPE_PROMPT_EXTEND,
            "watermark": settings.DASHSCOPE_WATERMARK,
        },
    )
    wan3 = Wan3VideoProvider(
        settings.WAN3_API_KEY,
        settings.WAN3_API_URL,
        settings.WAN3_MODEL,
        {
            "resolution": settings.WAN3_RESOLUTION,
            "ratio": settings.WAN3_RATIO,
            "duration": settings.WAN3_DURATION,
            "audio": settings.WAN3_AUDIO,
            "seed": settings.WAN3_SEED,
            "prompt_extend": settings.WAN3_PROMPT_EXTEND,
            "watermark": settings.WAN3_WATERMARK,
            "poll_interval": settings.WAN3_POLL_INTERVAL,
            "timeout": settings.WAN3_TIMEOUT,
        },
    )
    return {"mimo": mimo, "qwen": qwen, "wan3": wan3}


async def run_health(settings: Settings) -> int:
    providers = await _build_providers(settings)
    result: dict[str, object] = {}
    ok = True
    for name, provider in providers.items():
        started = time.time()
        try:
            healthy = await provider.health_check()
        except Exception as exc:  # noqa: BLE001 - 探测阶段要吞掉并如实上报
            healthy = False
            result[name] = {
                "healthy": False,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - started, 2),
            }
            ok = False
            continue
        result[name] = {
            "healthy": healthy,
            "elapsed_s": round(time.time() - started, 2),
        }
        ok = ok and healthy
    _out({"mode": "health", "providers": result, "all_healthy": ok})
    return 0 if ok else 1


async def run_models(settings: Settings) -> int:
    providers = await _build_providers(settings)
    result: dict[str, object] = {}
    for name, provider in providers.items():
        list_models = getattr(provider, "list_models", None)
        if list_models is None:
            result[name] = {"supported": False}
            continue
        try:
            models = await list_models()
            result[name] = {"supported": True, "models": models}
        except Exception as exc:  # noqa: BLE001
            result[name] = {"supported": True, "error": f"{type(exc).__name__}: {exc}"}
    _out({"mode": "models", "providers": result})
    return 0


async def run_chain(settings: Settings) -> int:
    """最小真实链路：MiMo 出 1 条分镜文本 -> Qwen 出 1 张图 -> Wan3 出 1 段短视频。

    调用量上限即上文三条；时长取配置里的 WAN3_DURATION（如需更省可先改 .env 为最小值）。
    """
    providers = await _build_providers(settings)
    out_dir = PROJECT_ROOT / "data" / "uat" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"mode": "chain", "out_dir": str(out_dir), "steps": []}

    def step(name: str, **payload: object) -> None:
        report["steps"].append({"step": name, **payload})  # type: ignore[union-attr]

    # 1. MiMo —— 1 次文本调用，产出 1 条 image_prompt
    started = time.time()
    try:
        text = await providers["mimo"].generate_text(
            "请只输出一句用于文生图的英文 prompt，主题：冬季单板滑雪教学，"
            "一位教练指导一位初学者，写实电影感，晴天雪道，背景无其他人。"
            "不要输出任何其它文字。",
            {"temperature": 0.7},
        )
        image_prompt = text.strip().splitlines()[0][:500]
        step(
            "mimo_text",
            ok=True,
            elapsed_s=round(time.time() - started, 2),
            image_prompt=image_prompt,
        )
    except Exception as exc:  # noqa: BLE001
        step("mimo_text", ok=False, error=f"{type(exc).__name__}: {exc}")
        _out(report)
        return 1

    # 2. Qwen Image —— 1 次生图
    started = time.time()
    try:
        image_bytes = await providers["qwen"].generate_image(image_prompt)
        image_path = out_dir / "scene-001-variant-01.png"
        image_path.write_bytes(image_bytes)
        step(
            "qwen_image",
            ok=True,
            elapsed_s=round(time.time() - started, 2),
            path=str(image_path),
            bytes_len=len(image_bytes),
        )
    except Exception as exc:  # noqa: BLE001
        step("qwen_image", ok=False, error=f"{type(exc).__name__}: {exc}")
        _out(report)
        return 1

    # 3. Wan3 —— 1 次生视频（图生视频，时长压到最小 2 秒以控成本）
    started = time.time()
    try:
        video_bytes = await providers["wan3"].generate_video(
            str(image_path),
            "镜头缓慢推近，人物保持单板姿态，动作连贯自然",
            {"duration": 2, "resolution": "480P"},
        )
        video_path = out_dir / "scene-001-variant-01.mp4"
        video_path.write_bytes(video_bytes)
        external_job_id = getattr(providers["wan3"], "get_external_job_id", lambda: None)()
        step(
            "wan3_video",
            ok=True,
            elapsed_s=round(time.time() - started, 2),
            path=str(video_path),
            bytes_len=len(video_bytes),
            external_job_id=external_job_id,
            duration_s=2,
        )
    except Exception as exc:  # noqa: BLE001
        step("wan3_video", ok=False, error=f"{type(exc).__name__}: {exc}")
        _out(report)
        return 1

    report["ok"] = True
    _out(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MiMo -> Qwen -> Wan3 minimal real-chain smoke")
    parser.add_argument("mode", choices=["health", "models", "chain"], help="探测或执行模式")
    args = parser.parse_args()

    # 不加载 .env 之外的隐藏覆盖；Settings 本身会读 .env
    settings = Settings(_env_file=PROJECT_ROOT / ".env")

    if args.mode == "health":
        return asyncio.run(run_health(settings))
    if args.mode == "models":
        return asyncio.run(run_models(settings))
    return asyncio.run(run_chain(settings))


if __name__ == "__main__":
    raise SystemExit(main())
