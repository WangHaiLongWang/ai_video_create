import re

from .models import NodeData, Position, WorkflowEdge, WorkflowNode, WorkflowSpec
from .schemas.node_catalog import load_node_catalog


NODE_DEFS = [
    ("textInput", "主题输入", None, "text", {"prompt": ""}),
    ("storyboard", "分镜生成", "text", "list<scene>", {"provider": "Mock", "scenes": 5}),
    ("textToImage", "文生图", "list<scene>", "list<image>", {"provider": "Mock", "mapOver": True}),
    ("imageToVideo", "图生视频", "list<image>", "list<video>", {"provider": "Mock", "duration": 4, "mapOver": True}),
    ("videoConcat", "视频合成", "list<video>", "video", {"transition": "crossfade"}),
    ("output", "成片输出", "video", None, {"filename": "output.mp4"}),
]


def _default_port_ids() -> dict[str, tuple[str | None, str | None]]:
    """从共享 catalog 推导 kind -> (输入端口, 输出端口)。

    HARD-101：端口 ID 来自 schemas/base-node-manifest.json。
    选第一个必填输入（若无则第一个输入）与第一个输出。
    边必须携带 sourceHandle/targetHandle 才能命中必填端口。
    """
    catalog = load_node_catalog()
    result: dict[str, tuple[str | None, str | None]] = {}
    for kind, manifest in catalog.items():
        inputs = manifest.ports.inputs
        outputs = manifest.ports.outputs
        in_id = next((p.id for p in inputs if p.required), inputs[0].id if inputs else None)
        out_id = outputs[0].id if outputs else None
        result[kind] = (in_id, out_id)
    return result


NODE_PORT_IDS: dict[str, tuple[str | None, str | None]] = _default_port_ids()


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
        WorkflowEdge(
            id=f"edge-{index}",
            source=nodes[index - 1].id,
            target=nodes[index].id,
            sourceHandle=NODE_PORT_IDS[nodes[index - 1].data.kind][1],
            targetHandle=NODE_PORT_IDS[nodes[index].data.kind][0],
        )
        for index in range(1, len(nodes))
    ]
    return WorkflowSpec(id="prompt-to-video", name="提示词到短视频", nodes=nodes, edges=edges)

