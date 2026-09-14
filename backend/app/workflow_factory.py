import re

from .models import NodeData, Position, WorkflowEdge, WorkflowNode, WorkflowSpec


NODE_DEFS = [
    ("textInput", "主题输入", None, "text", {"prompt": ""}),
    ("storyboard", "分镜生成", "text", "list<scene>", {"provider": "Mock", "scenes": 5}),
    ("textToImage", "文生图", "list<scene>", "list<image>", {"provider": "Mock", "mapOver": True}),
    ("imageToVideo", "图生视频", "list<image>", "list<video>", {"provider": "Mock", "duration": 4, "mapOver": True}),
    ("videoConcat", "视频合成", "list<video>", "video", {"transition": "crossfade"}),
    ("output", "成片输出", "video", None, {"filename": "output.mp4"}),
]


def create_prompt_to_video(prompt: str) -> WorkflowSpec:
    match = re.search(r"(\d+)\s*镜头", prompt)
    scene_count = max(1, min(int(match.group(1)) if match else 5, 20))
    nodes: list[WorkflowNode] = []
    for index, (kind, label, input_type, output_type, config) in enumerate(NODE_DEFS):
        node_config = dict(config)
        if kind == "textInput":
            node_config["prompt"] = prompt
        if kind == "storyboard":
            node_config["scenes"] = scene_count
        nodes.append(
            WorkflowNode(
                id=f"{kind}-1",
                position=Position(x=110 + index * 285, y=220 if index % 2 else 150),
                data=NodeData(
                    label=label,
                    description="由 Workflow Agent 生成",
                    kind=kind,
                    inputType=input_type,
                    outputType=output_type,
                    config=node_config,
                ),
            )
        )
    edges = [
        WorkflowEdge(id=f"edge-{index}", source=nodes[index - 1].id, target=nodes[index].id)
        for index in range(1, len(nodes))
    ]
    return WorkflowSpec(id="prompt-to-video", name="提示词到短视频", nodes=nodes, edges=edges)

