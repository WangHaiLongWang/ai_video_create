from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from pydantic import BaseModel

from .scene_bundle import SceneImagePrompt, ScenePromptBundle, SceneEntry, SceneVideoPrompt


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
        obj: dict[str, Any] = {
            "model": scene.image.model or "qwen-image-3.0",
            "prompt": scene.image.prompt,
            "negative_prompt": scene.image.negative_prompt or "",
            "size": scene.image.size or "1280x720",
        }
        if scene.image.seed != -1:
            obj["seed"] = scene.image.seed
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def export_to_wan3_jsonl(bundle: ScenePromptBundle) -> str:
    """One Wan3 video request JSON object per line."""
    lines: list[str] = []
    for scene in bundle.scenes:
        obj: dict[str, Any] = {
            "model": scene.video.model or "wan3.0-video",
            "prompt": scene.video.prompt,
            "resolution": scene.video.resolution or "480P",
            "ratio": scene.video.ratio or "adaptive",
            "duration": scene.video.duration or 5,
        }
        if scene.video.first_frame_asset_id:
            obj["firstFrame"] = scene.video.first_frame_asset_id
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
# Import helpers
# ---------------------------------------------------------------------------


class SceneImportError(Exception):
    """Raised when an import operation fails due to invalid data."""


def import_from_json(json_str: str) -> ScenePromptBundle:
    """Parse a JSON string into a ScenePromptBundle.

    Accepts both camelCase (by_alias) and snake_case key formats.
    Raises SceneImportError on invalid or missing required fields.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise SceneImportError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SceneImportError("JSON root must be an object, not an array or primitive")

    try:
        return ScenePromptBundle.model_validate(data)
    except Exception as exc:
        raise SceneImportError(f"Validation failed: {exc}") from exc


def _parse_csv_field(value: str) -> str:
    """Unescape a CSV field value (handles double-quote escaping)."""
    stripped = value.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        inner = stripped[1:-1]
        return inner.replace('""', '"')
    return stripped


def import_from_csv(csv_str: str) -> ScenePromptBundle:
    """Parse a CSV string (with optional BOM) into a ScenePromptBundle.

    The CSV must have the header row produced by export_to_csv:
      sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked

    Raises SceneImportError on invalid or incomplete data.
    """
    # Strip BOM if present
    text = csv_str.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    all_rows = [row for row in reader]

    if len(all_rows) < 2:
        raise SceneImportError("CSV must have a header row and at least one data row")

    header = all_rows[0]
    expected = ["sceneId", "index", "title", "narration", "durationSeconds", "image_prompt", "video_prompt", "locked"]
    if header != expected:
        raise SceneImportError(
            f"Unexpected CSV header. Expected: {','.join(expected)}\nGot: {','.join(header)}"
        )

    scenes: list[SceneEntry] = []
    for row_num, fields in enumerate(all_rows[1:], start=2):
        if len(fields) < 8:
            raise SceneImportError(f"Row {row_num}: expected 8 columns, got {len(fields)}")

        try:
            scene = SceneEntry(
                scene_id=fields[0],
                index=int(fields[1]),
                title=fields[2],
                narration=fields[3],
                duration_seconds=float(fields[4]),
                image=SceneImagePrompt(prompt=fields[5]),
                video=SceneVideoPrompt(prompt=fields[6]),
                locked=fields[7].lower() == "true",
            )
        except (ValueError, IndexError) as exc:
            raise SceneImportError(f"Row {row_num}: parse error: {exc}") from exc

        scenes.append(scene)

    return ScenePromptBundle(
        storyboard_id="imported-csv",
        workflow_id="imported-csv",
        execution_id="imported-csv",
        title="Imported from CSV",
        scenes=scenes,
    )


def import_from_text(text_str: str) -> ScenePromptBundle:
    """Parse a plain-text prompt list (produced by export_to_text) into a ScenePromptBundle.

    Extracts image and video prompts from [Scene N] blocks.
    Narration is not available in text format; defaults to the image prompt.

    Raises SceneImportError when no valid scene blocks are found.
    """
    scenes: list[SceneEntry] = []
    current_index: int | None = None
    image_prompt = ""
    video_prompt = ""

    def _flush() -> None:
        nonlocal current_index, image_prompt, video_prompt
        if current_index is not None:
            scenes.append(
                SceneEntry(
                    scene_id=f"imported-{current_index}",
                    index=current_index,
                    title=f"Scene {current_index}",
                    narration=image_prompt or f"Scene {current_index}",
                    image=SceneImagePrompt(prompt=image_prompt),
                    video=SceneVideoPrompt(prompt=video_prompt),
                )
            )
        current_index = None
        image_prompt = ""
        video_prompt = ""

    for line in text_str.split("\n"):
        stripped = line.strip()

        # Match [Scene N]
        m = re.match(r"^\[Scene\s+(\d+)\]$", stripped)
        if m:
            _flush()
            current_index = int(m.group(1))
            continue

        if stripped.startswith("Image: "):
            image_prompt = stripped[len("Image: "):]
        elif stripped.startswith("Video: "):
            video_prompt = stripped[len("Video: "):]

    # Flush the last scene
    _flush()

    if not scenes:
        raise SceneImportError("No [Scene N] blocks found in text input")

    return ScenePromptBundle(
        storyboard_id="imported-text",
        workflow_id="imported-text",
        execution_id="imported-text",
        title="Imported from Text",
        scenes=scenes,
    )


# ---------------------------------------------------------------------------
# Security scanner
# ---------------------------------------------------------------------------

_SECRET_KEY_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "sk-* secret key"),
    (re.compile(r"api_key\s*[=:]\s*\S+", re.IGNORECASE), "api_key assignment"),
    (re.compile(r"apikey\s*:\s*\S+", re.IGNORECASE), "apikey header"),
    (re.compile(r"token\s*:\s*\S+", re.IGNORECASE), "token header"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer token"),
]

_SIGNED_URL_PATTERNS = [
    (re.compile(r"[?&]Signature=[^&\s]+"), "AWS Signature"),
    (re.compile(r"[?&]X-Amz-Signature=[^&\s]+"), "AWS Amz Signature"),
    (re.compile(r"[?&]sig=[^&\s]+"), "sig parameter"),
    (re.compile(r"[?&]token=[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "signed token param"),
]

_ABSOLUTE_PATH_PATTERNS = [
    (re.compile(r"[A-Z]:\\[^\"'\s,]+"), "Windows path"),
    (re.compile(r"/(?:home|tmp|var|etc|usr|opt)/[^\"'\s,]+"), "Unix path"),
    (re.compile(r"\\\\[A-Za-z][^\"'\s,]+"), "UNC network path"),
]

_API_KEY_VAR_PATTERNS = [
    (re.compile(r"\$\{[A-Z_]*API[_-]?KEY[A-Z_]*\}", re.IGNORECASE), "${API_KEY} reference"),
    (re.compile(r"\$[A-Z_]*API[_-]?KEY[A-Z_]*", re.IGNORECASE), "$API_KEY variable"),
    (re.compile(r"process\.env\."), "process.env. reference"),
]

_EMAIL_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "email address"),
]

_IP_ADDRESS_PATTERNS = [
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "IP address"),
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
for pat, label in _EMAIL_PATTERNS:
    _ALL_PATTERNS.append((pat, "EMAIL", label, "warning"))
for pat, label in _IP_ADDRESS_PATTERNS:
    _ALL_PATTERNS.append((pat, "IP_ADDRESS", label, "warning"))


class SecurityIssue(BaseModel):
    severity: str  # "error" | "warning"
    code: str
    message: str
    scene_id: str | None = None
    field: str | None = None


def scan_for_secrets(text: str) -> list[SecurityIssue]:
    """Scan arbitrary text for security violations.

    Returns a list of SecurityIssue for every pattern match found.
    This is the low-level scanner that checks raw text content.
    """
    issues: list[SecurityIssue] = []
    for pat, code, label, severity in _ALL_PATTERNS:
        for match in pat.finditer(text):
            issues.append(SecurityIssue(
                severity=severity,
                code=code,
                message=f"Detected potential {label}",
                field="text",
            ))
            break  # one issue per pattern per call is enough
    return issues


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


def validate_export_safety(bundle: ScenePromptBundle) -> tuple[bool, list[SecurityIssue]]:
    """Validate that a bundle is safe to export.

    Returns (is_safe, issues). If is_safe is False the export must be blocked.
    Only "error" severity issues block the export; warnings are reported but allowed.
    """
    issues = scan_bundle_security(bundle)
    blocking = [i for i in issues if i.severity == "error"]
    return len(blocking) == 0, issues
