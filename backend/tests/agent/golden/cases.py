"""Golden test cases for the Agent intent compiler and tools.

Each case defines:
- id: unique identifier
- prompt: Chinese user prompt
- category: test category
- expected_nodes: list of (alias, kind) tuples in order
- expected_connections: list of (src_alias, src_port, tgt_alias, tgt_port, mode) tuples
- expected_config: dict of {alias: {key: value}} config overrides
- is_destructive: whether this operation removes/modifies existing data
- expect_validation_pass: whether validate_intent should pass
- expect_repair_needed: whether repair_intent should produce repairs
- expected_node_count: exact node count expected in compiled output
- expected_edge_count: exact edge count expected in compiled output
- notes: human-readable explanation
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GoldenCase:
    id: str
    prompt: str
    category: str
    expected_nodes: list[tuple[str, str]]
    expected_connections: list[tuple[str, str, str, str, str]]
    expected_config: dict[str, dict] = field(default_factory=dict)
    is_destructive: bool = False
    expect_validation_pass: bool = True
    expect_repair_needed: bool = False
    expected_node_count: int | None = None
    expected_edge_count: int | None = None
    tags: list[str] = field(default_factory=list)
    scene_count: int | None = None
    variant_count: int | None = None
    duration: int | None = None
    resolution: str | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Category 1: Basic generation (10 cases)
# ---------------------------------------------------------------------------

BASIC_GENERATION: list[GoldenCase] = [
    GoldenCase(
        id="basic-01-linear-pipeline",
        prompt="生成一个提示词到视频的流程",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="Standard prompt-to-video pipeline, the most common case.",
    ),
    GoldenCase(
        id="basic-02-storyboard-image-video-concat",
        prompt="创建分镜→图片→视频→合成的工作流",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="4-stage pipeline with input and output nodes.",
    ),
    GoldenCase(
        id="basic-03-provider-specific",
        prompt="用 Qwen 生图，Wan3 生视频",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={
            "img": {"provider": "Qwen"},
            "vid": {"provider": "Wan3"},
        },
        expected_node_count=6,
        expected_edge_count=5,
        notes="Provider-specific: Qwen for images, Wan3 for videos.",
    ),
    GoldenCase(
        id="basic-04-three-scenes",
        prompt="生成 3 个场景的短视频工作流",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"story": {"scenes": 3}},
        scene_count=3,
        expected_node_count=6,
        expected_edge_count=5,
        notes="Scene count explicitly specified as 3.",
    ),
    GoldenCase(
        id="basic-05-product-showcase",
        prompt="制作一个产品展示视频",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"story": {"style": "product"}},
        expected_node_count=6,
        expected_edge_count=5,
        notes="Product showcase template selection.",
    ),
    GoldenCase(
        id="basic-06-five-scenes-trailer",
        prompt="从一段文字生成 5 个镜头的预告片",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"story": {"scenes": 5}},
        scene_count=5,
        expected_node_count=6,
        expected_edge_count=5,
        notes="5-scene trailer generation.",
    ),
    GoldenCase(
        id="basic-07-image-only",
        prompt="创建一个图片风格转换流程",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
        ],
        expected_node_count=3,
        expected_edge_count=2,
        notes="Image-only pipeline: ends at image generation (no video/output).",
    ),
    GoldenCase(
        id="basic-08-text-only",
        prompt="搭建一个文本摘要工作流",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
        ],
        expected_node_count=2,
        expected_edge_count=1,
        notes="Text-only pipeline: input -> storyboard (no video/output).",
    ),
    GoldenCase(
        id="basic-09-model-specific",
        prompt="用 MiMo 模型分析文本并生成摘要",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"story": {"model": "MiMo"}},
        expected_node_count=6,
        expected_edge_count=5,
        notes="MiMo model specified for text analysis.",
    ),
    GoldenCase(
        id="basic-10-with-audio",
        prompt="生成一个带配音的短视频",
        category="basic_generation",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"story": {"with_audio": True}},
        expected_node_count=6,
        expected_edge_count=5,
        notes="Short video with voiceover/audio.",
    ),
]

# ---------------------------------------------------------------------------
# Category 2: Modification (8 cases)
# ---------------------------------------------------------------------------

MODIFICATION: list[GoldenCase] = [
    GoldenCase(
        id="mod-01-change-scene-count",
        prompt="把场景数从 3 改为 5",
        category="modification",
        expected_nodes=[
            ("story", "storyboard"),
        ],
        expected_connections=[],
        expected_config={"story": {"scenes": 5}},
        expected_node_count=1,
        expected_edge_count=0,
        notes="Simple config modification on storyboard node.",
    ),
    GoldenCase(
        id="mod-02-change-resolution",
        prompt="把图片分辨率改为 1920x1080",
        category="modification",
        expected_nodes=[
            ("img", "textToImage"),
        ],
        expected_connections=[],
        expected_config={"img": {"resolution": "1920x1080"}},
        resolution="1920x1080",
        expected_node_count=1,
        expected_edge_count=0,
        notes="Change image resolution parameter.",
    ),
    GoldenCase(
        id="mod-03-add-transition",
        prompt="在视频合成前加一个转场效果",
        category="modification",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("transition", "videoConcat"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "transition", "videos", "aggregate"),
            ("transition", "video", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=7,
        expected_edge_count=6,
        notes="Insert transition effect node before concat.",
    ),
    GoldenCase(
        id="mod-04-delete-output",
        prompt="删除输出节点",
        category="modification",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
        ],
        is_destructive=True,
        expected_node_count=5,
        expected_edge_count=4,
        notes="Removing output node is destructive (downstream loses input).",
    ),
    GoldenCase(
        id="mod-05-change-provider",
        prompt="把 Qwen 换成 Stable Diffusion",
        category="modification",
        expected_nodes=[
            ("img", "textToImage"),
        ],
        expected_connections=[],
        expected_config={"img": {"provider": "StableDiffusion"}},
        expected_node_count=1,
        expected_edge_count=0,
        notes="Change image generation provider.",
    ),
    GoldenCase(
        id="mod-06-insert-node",
        prompt="在 storyboard 和 image 之间插入一个文本处理节点",
        category="modification",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("refine", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "refine", "prompt", "map"),
            ("refine", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=7,
        expected_edge_count=6,
        notes="Insert a refinement storyboard node between story and image generation.",
    ),
    GoldenCase(
        id="mod-07-increase-variants",
        prompt="增加变体数从 2 到 4",
        category="modification",
        expected_nodes=[
            ("img", "textToImage"),
        ],
        expected_connections=[],
        expected_config={"img": {"variantCount": 4}},
        variant_count=4,
        expected_node_count=1,
        expected_edge_count=0,
        notes="Increase variant count for image generation.",
    ),
    GoldenCase(
        id="mod-08-batch-duration",
        prompt="把所有视频时长改为 5 秒",
        category="modification",
        expected_nodes=[
            ("vid", "imageToVideo"),
        ],
        expected_connections=[],
        expected_config={"vid": {"duration": 5}},
        duration=5,
        expected_node_count=1,
        expected_edge_count=0,
        notes="Batch modify video duration to 5 seconds.",
    ),
]

# ---------------------------------------------------------------------------
# Category 3: Validation and repair (7 cases)
# ---------------------------------------------------------------------------

VALIDATION_REPAIR: list[GoldenCase] = [
    GoldenCase(
        id="vr-01-validate-only",
        prompt="生成流程后验证是否合法",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expect_validation_pass=True,
        expected_node_count=6,
        expected_edge_count=5,
        notes="Standard pipeline should validate cleanly.",
    ),
    GoldenCase(
        id="vr-02-repair-disconnected",
        prompt="修复一个有断开连接的工作流",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("story", "storyboard"),  # duplicate alias -> auto-repaired
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=7,
        expected_edge_count=5,
        notes="Broken workflow: duplicate alias 'story' causes DUPLICATE_ALIAS error.",
    ),
    GoldenCase(
        id="vr-03-repair-cycle",
        prompt="修复一个有循环的工作流",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "story", "prompt", "direct"),  # cycle!
        ],
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=4,
        expected_edge_count=3,
        notes="Cyclic workflow: vid -> story creates a loop.",
    ),
    GoldenCase(
        id="vr-04-repair-missing-required",
        prompt="修复缺少必要输入的节点",
        category="validation_repair",
        expected_nodes=[
            ("story", "storyboard"),
            ("story", "storyboard"),  # duplicate alias
            ("img", "textToImage"),
        ],
        expected_connections=[],
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=3,
        expected_edge_count=0,
        notes="Duplicate alias 'story' with unconnected required inputs.",
    ),
    GoldenCase(
        id="vr-05-preflight-check",
        prompt="检查这个工作流能否运行",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expect_validation_pass=True,
        expected_node_count=6,
        expected_edge_count=5,
        notes="Pre-flight check on a valid pipeline.",
    ),
    GoldenCase(
        id="vr-06-diagnosis",
        prompt="这个工作流有什么问题",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            # Duplicate connection: same source->target port pair
            ("in", "text", "story", "prompt", "direct"),
        ],
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=4,
        expected_edge_count=2,
        notes="Diagnosis: duplicate connection on in.text->story.prompt.",
    ),
    GoldenCase(
        id="vr-07-optimize-layout",
        prompt="帮我优化这个工作流的执行顺序",
        category="validation_repair",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expect_validation_pass=True,
        expected_node_count=6,
        expected_edge_count=5,
        notes="Layout optimization of a valid pipeline.",
    ),
]

# ---------------------------------------------------------------------------
# Category 4: Destructive/cautious operations (5 cases)
# ---------------------------------------------------------------------------

DESTRUCTIVE: list[GoldenCase] = [
    GoldenCase(
        id="dest-01-delete-storyboard",
        prompt="删除 storyboard 节点",
        category="destructive",
        expected_nodes=[
            ("in", "textInput"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            # TYPE_MISMATCH: text -> scene (storyboard removed, broken pipeline)
            ("in", "text", "img", "scene", "direct"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        is_destructive=True,
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=5,
        expected_edge_count=4,
        notes="Deleting storyboard breaks pipeline: text->scene TYPE_MISMATCH.",
    ),
    GoldenCase(
        id="dest-02-replace-image-with-video",
        prompt="把所有图片节点替换为视频节点",
        category="destructive",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            # TYPE_MISMATCH: scene -> image (storyboard scenes can't go to video node)
            ("story", "scenes", "vid", "image", "direct"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        is_destructive=True,
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=5,
        expected_edge_count=4,
        notes="Major rewrite with TYPE_MISMATCH: scene->image is invalid.",
    ),
    GoldenCase(
        id="dest-03-disconnect-all",
        prompt="清空所有连线",
        category="destructive",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            # After "disconnect all", a wrong-type leftover causes TYPE_MISMATCH
            ("in", "text", "img", "scene", "direct"),
        ],
        is_destructive=True,
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=6,
        expected_edge_count=1,
        notes="After clearing all connections, a stray wrong-type connection remains.",
    ),
    GoldenCase(
        id="dest-04-reduce-scenes",
        prompt="把 5 个场景减为 1 个",
        category="destructive",
        expected_nodes=[
            ("story", "storyboard"),
        ],
        expected_connections=[],
        expected_config={"story": {"scenes": 1}},
        is_destructive=True,
        scene_count=1,
        expected_node_count=1,
        expected_edge_count=0,
        notes="Data loss risk: reducing scenes from 5 to 1.",
    ),
    GoldenCase(
        id="dest-05-switch-output-format",
        prompt="切换输出格式从 MP4 到 GIF",
        category="destructive",
        expected_nodes=[
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_config={"concat": {"filename": "output.gif"}},
        is_destructive=True,
        expected_node_count=2,
        expected_edge_count=1,
        notes="Format change from MP4 to GIF affects downstream.",
    ),
]

# ---------------------------------------------------------------------------
# Category 5: Edge cases (5+ cases)
# ---------------------------------------------------------------------------

EDGE_CASES: list[GoldenCase] = [
    GoldenCase(
        id="edge-01-empty-prompt",
        prompt="",
        category="edge_case",
        expected_nodes=[],
        expected_connections=[],
        expect_validation_pass=False,
        notes="Empty prompt should return error or default template.",
    ),
    GoldenCase(
        id="edge-02-very-long-prompt",
        prompt="生成一个视频" * 100,  # 500+ chars
        category="edge_case",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="Very long prompt (500+ chars) should be handled gracefully.",
    ),
    GoldenCase(
        id="edge-03-no-clear-intent",
        prompt="这个东西不错",
        category="edge_case",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="No clear intent: should use default pipeline template.",
    ),
    GoldenCase(
        id="edge-04-vague-prompt",
        prompt="帮我做一个视频",
        category="edge_case",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="Vague prompt: should generate reasonable default.",
    ),
    GoldenCase(
        id="edge-05-special-characters",
        prompt='生成 "引号" 和 <标签> 的流程',
        category="edge_case",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="Special characters in prompt should not break parsing.",
    ),
    GoldenCase(
        id="edge-06-chinese-english-mix",
        prompt="创建一个 tutorial 视频 about Python 编程",
        category="edge_case",
        expected_nodes=[
            ("in", "textInput"),
            ("story", "storyboard"),
            ("img", "textToImage"),
            ("vid", "imageToVideo"),
            ("concat", "videoConcat"),
            ("out", "output"),
        ],
        expected_connections=[
            ("in", "text", "story", "prompt", "direct"),
            ("story", "scenes", "img", "scene", "map"),
            ("img", "images", "vid", "image", "map"),
            ("vid", "videos", "concat", "videos", "aggregate"),
            ("concat", "video", "out", "video", "direct"),
        ],
        expected_node_count=6,
        expected_edge_count=5,
        notes="Mixed Chinese/English prompt.",
    ),
    GoldenCase(
        id="edge-07-malformed-intent-self-loop",
        prompt="自循环测试",
        category="edge_case",
        expected_nodes=[
            ("story", "storyboard"),
        ],
        expected_connections=[
            ("story", "scenes", "story", "prompt", "direct"),  # self-loop!
        ],
        expect_validation_pass=False,
        expect_repair_needed=True,
        expected_node_count=1,
        expected_edge_count=0,
        notes="Self-loop connection should be detected and repaired.",
    ),
]

# ---------------------------------------------------------------------------
# All cases combined
# ---------------------------------------------------------------------------

ALL_GOLDEN_CASES: list[GoldenCase] = (
    BASIC_GENERATION
    + MODIFICATION
    + VALIDATION_REPAIR
    + DESTRUCTIVE
    + EDGE_CASES
)

# Lookup by id
CASES_BY_ID: dict[str, GoldenCase] = {c.id: c for c in ALL_GOLDEN_CASES}

# Cases grouped by category
CASES_BY_CATEGORY: dict[str, list[GoldenCase]] = {}
for _case in ALL_GOLDEN_CASES:
    CASES_BY_CATEGORY.setdefault(_case.category, []).append(_case)
