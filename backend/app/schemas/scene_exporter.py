from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from .scene_bundle import ScenePromptBundle, SceneEntry


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_to_json(bundle: ScenePromptBundle) -> str:
    """Serialize the bundle to a JSON string."""
    return bundle.model_dump_json(indent=2, by_alias=True)


def export_to_markdown(bundle: ScenePromptBundle) -> str:
    """Render the bundle as a Markdown document."""
    lines: list[str] = []
    lines.append(f"# {bundle.title}")
    lines.append("")

    if bundle.global_style:
        lines.append(f"Global Style: {bundle.global_style}")
    if bundle.negative_prompt:
        lines.append(f"Negative: {bundle.negative_prompt}")
    if bundle.global_style or bundle.negative_prompt:
        lines.append("")

    for i, scene in enumerate(bundle.scenes):
        lines.append(f"## Scene {scene.index}: {scene.title}")
        lines.append("")
        lines.append(f"**Narration:** {scene.narration}")
        lines.append(f"**Duration:** {scene.duration_seconds}s")
        lines.append(f"**Image Prompt:** {scene.image.prompt}")
        lines.append(f"**Video Prompt:** {scene.video.prompt}")

        if i < len(bundle.scenes) - 1:
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def _escape_csv_field(value: str) -> str:
    if any(c in value for c in (',', '"', '\n')):
        return '"' + value.replace('"', '""') + '"'
    return value


def export_to_csv(bundle: ScenePromptBundle) -> str:
    """Export the bundle as CSV with UTF-8 BOM."""
    BOM = "﻿"
    header = "sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked"
    rows: list[str] = []
    for scene in bundle.scenes:
        row = ",".join([
            _escape_csv_field(scene.scene_id),
            str(scene.index),
            _escape_csv_field(scene.title),
            _escape_csv_field(scene.narration),
            str(scene.duration_seconds),
            _escape_csv_field(scene.image.prompt),
            _escape_csv_field(scene.video.prompt),
            str(scene.locked),
        ])
        rows.append(row)

    return BOM + header + "\n" + "\n".join(rows) + "\n"


def export_to_text(bundle: ScenePromptBundle) -> str:
    """Plain-text prompt list, one scene block separated by blank lines."""
    sections: list[str] = []
    for scene in bundle.scenes:
        sections.append(f"[Scene {scene.index}]")
        sections.append(f"Image: {scene.image.prompt}")
        sections.append(f"Video: {scene.video.prompt}")
        sections.append("")
    return "\n".join(sections)


def export_to_qwen_jsonl(bundle: ScenePromptBundle) -> str:
    """One Qwen image request JSON object per line."""
    lines: list[str] = []
    for scene in bundle.scenes:
        obj = {
            "model": scene.image.model or "qwen-image-3.0",
            "prompt": scene.image.prompt,
            "negative_prompt": scene.image.negative_prompt or "",
            "size": scene.image.size or "1280x720",
        }
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def export_to_wan3_jsonl(bundle: ScenePromptBundle) -> str:
    """One Wan3 video request JSON object per line."""
    lines: list[str] = []
    for scene in bundle.scenes:
        obj = {
            "model": scene.video.model or "wan3.0-video",
            "prompt": scene.video.prompt,
            "resolution": scene.video.resolution or "480P",
            "ratio": scene.video.ratio or "adaptive",
            "duration": scene.video.duration or 5,
        }
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def export_to_jsonl(bundle: ScenePromptBundle) -> str:
    """Generic JSONL export -- one JSON object per scene."""
    lines: list[str] = []
    for scene in bundle.scenes:
        obj = scene.model_dump(by_alias=True)
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Security scanner
# ---------------------------------------------------------------------------

_SECRET_KEY_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "sk-* secret key"),
    (re.compile(r"api_key\s*[=:]\s*\S+", re.IGNORECASE), "api_key assignment"),
    (re.compile(r"apikey\s*:\s*\S+", re.IGNORECASE), "apikey header"),
    (re.compile(r"token\s*:\s*\S+", re.IGNORECASE), "token header"),
]

_SIGNED_URL_PATTERNS = [
    (re.compile(r"[?&]Signature=[^&]+"), "AWS Signature"),
    (re.compile(r"[?&]X-Amz-Signature=[^&]+"), "AWS Amz Signature"),
    (re.compile(r"[?&]sig=[^&]+"), "sig parameter"),
]

_ABSOLUTE_PATH_PATTERNS = [
    (re.compile(r"[A-Z]:\\[^\"'\s,]+"), "Windows path"),
    (re.compile(r"/(?:home|tmp|var|etc|usr|opt)/[^\"'\s,]+"), "Unix path"),
]

_API_KEY_VAR_PATTERNS = [
    (re.compile(r"\$\{[A-Z_]*API[_-]?KEY[A-Z_]*\}", re.IGNORECASE), "${API_KEY} reference"),
    (re.compile(r"\$[A-Z_]*API[_-]?KEY[A-Z_]*", re.IGNORECASE), "$API_KEY variable"),
    (re.compile(r"process\.env\."), "process.env. reference"),
]

_ALL_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = []
for pat, label in _SECRET_KEY_PATTERNS:
    _ALL_PATTERNS.append((pat, "SECRET_KEY", label, "error"))
for pat, label in _SIGNED_URL_PATTERNS:
    _ALL_PATTERNS.append((pat, "SIGNED_URL", label, "error"))
for pat, label in _ABSOLUTE_PATH_PATTERNS:
    _ALL_PATTERNS.append((pat, "ABSOLUTE_PATH", label, "warning"))
for pat, label in _API_KEY_VAR_PATTERNS:
    _ALL_PATTERNS.append((pat, "API_KEY", label, "error"))


class SecurityIssue(BaseModel):
    severity: str  # "error" | "warning"
    code: str
    message: str
    scene_id: str | None = None
    field: str | None = None


def _check_text(text: str, scene_id: str | None, field: str) -> list[SecurityIssue]:
    issues: list[SecurityIssue] = []
    for pat, code, label, severity in _ALL_PATTERNS:
        if pat.search(text):
            issues.append(SecurityIssue(
                severity=severity,
                code=code,
                message=f"Detected potential {label} in {field}",
                scene_id=scene_id,
                field=field,
            ))
    return issues


def _scan_scene(scene: SceneEntry) -> list[SecurityIssue]:
    issues: list[SecurityIssue] = []
    sid = scene.scene_id

    issues.extend(_check_text(scene.narration, sid, "narration"))
    issues.extend(_check_text(scene.image.prompt, sid, "image.prompt"))
    if scene.image.negative_prompt:
        issues.extend(_check_text(scene.image.negative_prompt, sid, "image.negativePrompt"))
    issues.extend(_check_text(scene.video.prompt, sid, "video.prompt"))
    issues.extend(_check_text(scene.title, sid, "title"))

    return issues


def scan_bundle_security(bundle: ScenePromptBundle) -> list[SecurityIssue]:
    """Scan the entire bundle for security issues."""
    issues: list[SecurityIssue] = []

    issues.extend(_check_text(bundle.title, None, "bundle.title"))
    if bundle.global_style:
        issues.extend(_check_text(bundle.global_style, None, "bundle.globalStyle"))
    if bundle.negative_prompt:
        issues.extend(_check_text(bundle.negative_prompt, None, "bundle.negativePrompt"))

    for scene in bundle.scenes:
        issues.extend(_scan_scene(scene))

    return issues
