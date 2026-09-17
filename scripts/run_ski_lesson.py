"""Run the 冬季单板滑雪教学 workflow end-to-end with real providers.

Usage:
    python scripts/run_ski_lesson.py

Produces:
    - 2 images (variant-01, variant-02)
    - 2 videos (3s each)
    - 1 final concatenated video (~6s)
    All assets saved to data/assets/
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.app.config import get_settings
    from backend.app.db.connection import close_connection, init_db, get_connection
    from backend.app.engine.compiler import compile_workflow
    from backend.app.engine.queue import get_tasks_by_execution
    from backend.app.engine.scheduler import Scheduler
    from backend.app.handlers import init_real_handlers
    from backend.app.handlers.contracts import NodeResult, ArtifactRef, NodeError
    from backend.app.services.templates import get_template_service
    from backend.app.engine.queue import get_upstream_results

    settings = get_settings()
    print("=" * 60)
    print("冬季单板滑雪教学 — 真实 Provider 执行")
    print("=" * 60)
    print(f"Image Provider: {settings.DEFAULT_IMAGE_PROVIDER.value}")
    print(f"Image Model:    {settings.DASHSCOPE_IMAGE_MODEL}")
    print(f"Video Provider: {settings.DEFAULT_VIDEO_PROVIDER.value}")
    print(f"Video Model:    {settings.WAN3_MODEL}")
    print()

    # 1. Initialize DB (clean slate for this run)
    close_connection()
    # Remove old database to start fresh
    import os
    db_path = Path(settings.DB_PATH)
    if db_path.exists():
        os.remove(db_path)
    init_db()
    print("[1/8] Database initialized (fresh)")

    # 2. Initialize real providers and handlers
    from backend.app.providers import init_providers
    wan3_config = {
        "resolution": settings.WAN3_RESOLUTION,
        "ratio": settings.WAN3_RATIO,
        "duration": settings.WAN3_DURATION,
        "audio": settings.WAN3_AUDIO,
        "seed": settings.WAN3_SEED,
        "prompt_extend": settings.WAN3_PROMPT_EXTEND,
        "watermark": settings.WAN3_WATERMARK,
        "poll_interval": settings.WAN3_POLL_INTERVAL,
        "timeout": settings.WAN3_TIMEOUT,
    }
    init_providers(
        mock=False,
        dashscope_key=settings.DASHSCOPE_API_KEY,
        dashscope_url=settings.DASHSCOPE_API_URL,
        dashscope_image_model=settings.DASHSCOPE_IMAGE_MODEL,
        dashscope_default_config={
            "size": settings.DASHSCOPE_IMAGE_SIZE,
            "use_async": settings.DASHSCOPE_USE_ASYNC,
            "prompt_extend": settings.DASHSCOPE_PROMPT_EXTEND,
            "prompt_extend_mode": settings.DASHSCOPE_PROMPT_EXTEND_MODE,
            "enable_thinking": settings.DASHSCOPE_ENABLE_THINKING,
            "watermark": settings.DASHSCOPE_WATERMARK,
        },
        wan3_key=settings.WAN3_API_KEY,
        wan3_url=settings.WAN3_API_URL,
        wan3_model=settings.WAN3_MODEL,
        wan3_default_config=wan3_config,
    )
    init_real_handlers()
    print("[2/8] Real providers and handlers initialized")

    # 3. Load template
    svc = get_template_service()
    detail = svc.get_template("realistic-ski-lesson")
    if not detail:
        print("ERROR: realistic-ski-lesson template not found!")
        return
    print(f"[3/8] Template loaded: {detail.name}")

    # 4. Create workflow from template with prompt
    ski_prompt = (
        "冬季单板滑雪教学，晴朗白天，初级雪道。"
        "教练在左侧，双脚固定，半蹲讲解；学员在右侧，仅前脚固定，后脚自由蹬行。"
        "背景无人，写实电影感。"
    )
    spec = svc.create_from_template(
        "realistic-ski-lesson",
        params={"prompt": ski_prompt},
    )
    print(f"[4/8] Workflow created: {spec.id}")

    # 5. Compile and check task count
    spec_dict = {
        "id": spec.id,
        "name": spec.name,
        "nodes": [
            {
                "id": n.id,
                "type": n.type,
                "position": {"x": n.position.x, "y": n.position.y},
                "data": {
                    "kind": n.data.kind,
                    "label": n.data.label,
                    "config": n.data.config,
                },
            }
            for n in spec.nodes
        ],
        "edges": [
            {"id": e.id, "source": e.source, "target": e.target, "type": e.type}
            for e in spec.edges
        ],
    }
    plan = compile_workflow(spec_dict)
    print(f"[5/8] Compiled: {len(plan.tasks)} tasks")
    for t in plan.tasks:
        variant = t.config.get("variant_id", "")
        suffix = f" ({variant})" if variant else ""
        print(f"       - {t.id}{suffix}")

    # 6. Create execution record
    conn = get_connection()
    execution_id = f"exec-ski-{int(time.time())}"
    spec_json = json.dumps(spec_dict, ensure_ascii=False)
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        (spec.id, spec.name, spec_json),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        (execution_id, spec.id, spec_json, "pending"),
    )
    conn.commit()
    print(f"[6/8] Execution created: {execution_id}")

    # 7. Run pipeline
    print("[7/8] Starting execution...")
    scheduler = Scheduler(max_retries=2, poll_interval=1.0)

    ready = await scheduler.start_execution(execution_id)
    print(f"       Initial ready tasks: {ready}")

    start_time = time.time()
    max_wait = 900  # 15 minutes max

    while not scheduler.check_convergence(execution_id):
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"       TIMEOUT after {elapsed:.0f}s!")
            break

        tasks = get_tasks_by_execution(execution_id)
        ready_tasks = [
            t for t in tasks
            if t["status"] == "pending"
            and all(
                next((tt for tt in tasks if tt["id"] == d), None) is not None
                and next(tt for tt in tasks if tt["id"] == d)["status"] == "completed"
                for d in t.get("depends_on", [])
            )
        ]

        if not ready_tasks:
            # Show status
            running = [t for t in tasks if t["status"] == "running"]
            pending = [t for t in tasks if t["status"] == "pending"]
            completed = [t for t in tasks if t["status"] == "completed"]
            failed = [t for t in tasks if t["status"] == "failed"]
            print(
                f"\r       [{elapsed:.0f}s] "
                f"completed={len(completed)} running={len(running)} "
                f"pending={len(pending)} failed={len(failed)}",
                end="", flush=True,
            )
            await asyncio.sleep(2)
            continue

        for task in ready_tasks:
            task_id = task["id"]
            kind = task["kind"]
            item_key = task.get("item_key", "")
            variant = task.get("config", {}).get("variant_id", "")
            label = f"{kind}" + (f" ({variant})" if variant else "")
            print(f"\n       -> Executing: {task_id} [{label}]")

            # Assemble input
            task = scheduler.assemble_node_input(task, execution_id)

            # Pass upstream results to handler context
            depends_on = task.get("depends_on", [])
            upstream_results = get_upstream_results(execution_id, depends_on) if depends_on else {}
            context = {"upstream_results": upstream_results}

            # Get handler
            from backend.app.handlers import get_handler
            handler = get_handler(kind)
            if not handler:
                print(f"         ERROR: No handler for {kind}")
                await scheduler.fail_task(
                    task_id,
                    NodeError(code="NO_HANDLER", message=f"No handler for {kind}"),
                )
                continue

            try:
                t0 = time.time()
                result = await handler.execute(task, context)
                dt = time.time() - t0

                if result.status == "failed":
                    error_msg = result.error.message if result.error else "unknown"
                    print(f"         [FAIL] FAILED ({dt:.1f}s): {error_msg}")
                    await scheduler.fail_task(
                        task_id,
                        result.error or NodeError(code="UNKNOWN", message="unknown"),
                    )
                else:
                    asset_info = ""
                    if result.output:
                        if result.output.asset_id:
                            asset_info += f" asset={result.output.asset_id}"
                        if result.output.url:
                            asset_info += f" url={result.output.url}"
                        meta = result.output.metadata
                        if meta.get("path"):
                            asset_info += f" path={meta['path']}"
                    print(f"         [OK] OK ({dt:.1f}s){asset_info}")
                    await scheduler.complete_task(task_id, result)
                    # Trigger downstream scheduling
                    await scheduler.schedule_next_tasks(execution_id)

            except Exception as e:
                print(f"         [FAIL] EXCEPTION: {e}")
                await scheduler.fail_task(
                    task_id,
                    NodeError(code="EXCEPTION", message=str(e)),
                )

    elapsed = time.time() - start_time
    print(f"\n\n[8/8] Execution completed in {elapsed:.1f}s")

    # 8. Report results
    summary = scheduler.get_execution_summary(execution_id)
    print("\n" + "=" * 60)
    print("执行摘要")
    print("=" * 60)
    print(f"  总任务数: {summary.get('total', 0)}")
    print(f"  成功:     {summary.get('completed', 0)}")
    print(f"  失败:     {summary.get('failed', 0)}")
    print(f"  跳过:     {summary.get('skipped', 0)}")
    print(f"  取消:     {summary.get('cancelled', 0)}")

    # List generated assets
    conn = get_connection()
    exec_row = conn.execute(
        "SELECT status FROM executions WHERE id = ?", (execution_id,)
    ).fetchone()
    print(f"\n  Execution 状态: {exec_row['status'] if exec_row else 'unknown'}")

    # List all tasks with results
    task_rows = conn.execute(
        "SELECT id, kind, status, result_json FROM tasks "
        "WHERE execution_id = ? ORDER BY task_index, id",
        (execution_id,),
    ).fetchall()

    print("\n  任务详情:")
    for row in task_rows:
        result = json.loads(row["result_json"]) if row["result_json"] else {}
        output = result.get("output", {})
        path = output.get("metadata", {}).get("path", "")
        asset_id = output.get("asset_id", "")
        status_icon = "[OK]" if row["status"] == "completed" else "[FAIL]" if row["status"] == "failed" else "[..]"
        detail = f"asset={asset_id}" if asset_id else ""
        if path:
            detail += f" path={path}"
        print(f"    {status_icon} {row['id']}: {row['status']} {detail}")

    # Print asset directory
    asset_dir = Path("data/assets")
    if asset_dir.exists():
        print(f"\n  生成的文件 ({asset_dir}):")
        for f in sorted(asset_dir.rglob("*")):
            if f.is_file():
                size = f.stat().st_size
                print(f"    {f.relative_to(asset_dir)} ({size:,} bytes)")

    close_connection()
    print("\n" + "=" * 60)
    print("完成!")


if __name__ == "__main__":
    asyncio.run(main())
