"""Ski lesson workflow fixtures — Scene Bundle and WorkflowSpec.

These fixtures define the "冬季单板滑雪教学" acceptance workflow:
- 1 Scene with 2 image variants
- 2 x 3s Wan3 videos
- Concatenated into ~6s final video
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Scene Prompt Bundle (SKI-LESSON-WORKFLOW-PLAN section 4)
# ---------------------------------------------------------------------------

SKI_LESSON_SCENE_BUNDLE = {
    "schemaVersion": "1.0",
    "storyboardId": "ski-lesson-storyboard",
    "workflowId": "template-ski-lesson",
    "executionId": "",
    "title": "冬季单板滑雪单脚蹬行教学",
    "globalStyle": (
        "写实电影感，晴朗冬季白天，低机位35mm，自然光，浅景深，"
        "4K冬季运动摄影"
    ),
    "negativePrompt": (
        "第三个人，背景人物，人群，双板滑雪，错误固定器，肢体畸形，"
        "文字，水印"
    ),
    "source": "draft",
    "scenes": [
        {
            "sceneId": "scene-001",
            "index": 0,
            "title": "单脚蹬行姿势讲解",
            "narration": "教练讲解前脚固定、后脚自由的单脚蹬行准备姿势。",
            "durationSeconds": 3,
            "locked": True,
            "image": {
                "prompt": (
                    "写实电影感冬季单板滑雪教学照片，晴朗白天，平缓的初级雪道。"
                    "画面严格只有两个人，背景没有任何其他人物。\n\n"
                    "左侧是一位单板滑雪教练，双脚都固定在同一块单板滑雪板的固定器中，"
                    "保持稳定半蹲姿势，一只手向前伸出，手指明确指向右侧学员的前脚固定器，"
                    "神态专注耐心，正在讲解如何单脚蹬行。\n\n"
                    "右侧是一位初学者学员，站在自己的单板滑雪板上，仅前脚固定在前脚固定器内，"
                    "后脚完全未固定并踩在雪地上准备蹬行；膝盖微屈，身体侧向，视线看向前方，"
                    "板头清晰指向预定滑行方向。两人的滑雪板彼此独立，装备结构合理，"
                    "肢体与固定器关系清晰准确。\n\n"
                    "雪面有真实滑痕和轻微飞溅雪粒，远处雪山与缆车自然虚化。"
                    "中景，低机位，35mm 镜头，浅景深，自然阳光，真实雪地反射，"
                    "电影级色彩，4K，超写实，高细节，专业冬季运动摄影，"
                    "清晰准确的人体比例、手脚和单板固定器。"
                ),
                "negativePrompt": (
                    "第三个人，背景人物，人群，其他滑雪者，多余人物，双板滑雪，"
                    "滑雪杖，两人共用一块单板，学员双脚都固定，学员后脚固定在板上，"
                    "教练脚未固定，错误固定器，额外的腿，额外的手，多余手指，"
                    "肢体融合，手指方向错误，板头方向错误，单板断裂，装备漂浮，"
                    "错误透视，卡通，插画，CG 感，低清晰度，模糊，过曝，"
                    "文字，标志，水印"
                ),
                "provider": "dashscope",
                "model": "qwen-image-3.0",
                "size": "1280x720",
                "seed": -1,
                "referenceAssetIds": [],
            },
            "video": {
                "prompt": (
                    "保持首帧中的两个人、左右位置、服装、单板和固定器结构完全一致。"
                    "镜头进行非常轻微、平稳的低机位前推。"
                    "左侧教练保持半蹲，一只手继续指向学员前脚固定器并做小幅自然讲解手势；"
                    "右侧学员前脚保持固定、后脚保持自由并在雪地上轻轻蹬行一次，"
                    "膝盖微屈，板头持续朝向滑行方向。"
                    "雪面产生少量真实雪粒，远处雪山与缆车保持虚化。"
                    "不要新增人物，不要切镜，不要改变装备，不要让后脚自动固定，"
                    "不要改变为双板滑雪。写实电影感，自然日光，运动摄影，时长 3 秒。"
                ),
                "provider": "wan3",
                "model": "wan3.0-video",
                "resolution": "480P",
                "ratio": "16:9",
                "duration": 3,
                "audio": False,
                "seed": -1,
                "firstFrameAssetId": None,
            },
            "transition": {"type": "crossfade", "duration": 0.3},
            "metadata": {
                "variantCount": 2,
                "outputStrategy": "two_variants_to_video",
                "peopleCount": 2,
                "backgroundPeopleAllowed": False,
            },
        }
    ],
}

# ---------------------------------------------------------------------------
# Image variant definitions (per-scene variant prompt suffixes)
# ---------------------------------------------------------------------------

SKI_LESSON_VARIANTS = [
    {
        "id": "variant-01",
        "promptSuffix": (
            "略偏教练方向的低机位三分之四侧视角，突出教练指向固定器的手势"
        ),
    },
    {
        "id": "variant-02",
        "promptSuffix": (
            "低机位略宽中景，学员单脚蹬行准备姿态更清晰，雪粒略有动态"
        ),
    },
]

# ---------------------------------------------------------------------------
# WorkflowSpec for the ski lesson template
# ---------------------------------------------------------------------------

SKI_LESSON_WORKFLOW_SPEC = {
    "id": "template-ski-lesson",
    "name": "写实滑雪教学",
    "nodes": [
        {
            "id": "textInput",
            "type": "studio",
            "position": {"x": 100, "y": 200},
            "data": {
                "kind": "textInput",
                "label": "教学描述",
                "config": {"prompt": ""},
            },
        },
        {
            "id": "storyboard",
            "type": "studio",
            "position": {"x": 350, "y": 200},
            "data": {
                "kind": "storyboard",
                "label": "分镜生成",
                "config": {"scenes": 1, "style": "写实电影感"},
            },
        },
        {
            "id": "textToImage",
            "type": "studio",
            "position": {"x": 600, "y": 200},
            "data": {
                "kind": "textToImage",
                "label": "生成图片（双变体）",
                "config": {
                    "mapOver": True,
                    "variantCount": 2,
                    "variants": SKI_LESSON_VARIANTS,
                },
            },
        },
        {
            "id": "imageToVideo",
            "type": "studio",
            "position": {"x": 850, "y": 200},
            "data": {
                "kind": "imageToVideo",
                "label": "图片转视频",
                "config": {"mapOver": True, "variantCount": 2, "duration": 3, "resolution": "480P"},
            },
        },
        {
            "id": "videoConcat",
            "type": "studio",
            "position": {"x": 1100, "y": 200},
            "data": {
                "kind": "videoConcat",
                "label": "合成视频",
                "config": {"filename": "ski-lesson-final.mp4"},
            },
        },
        {
            "id": "output",
            "type": "studio",
            "position": {"x": 1350, "y": 200},
            "data": {
                "kind": "output",
                "label": "输出",
                "config": {},
            },
        },
    ],
    "edges": [
        {"id": "e1-2", "source": "textInput", "target": "storyboard", "type": "smoothstep"},
        {"id": "e2-3", "source": "storyboard", "target": "textToImage", "type": "smoothstep"},
        {"id": "e3-4", "source": "textToImage", "target": "imageToVideo", "type": "smoothstep"},
        {"id": "e4-5", "source": "imageToVideo", "target": "videoConcat", "type": "smoothstep"},
        {"id": "e5-6", "source": "videoConcat", "target": "output", "type": "smoothstep"},
    ],
}
