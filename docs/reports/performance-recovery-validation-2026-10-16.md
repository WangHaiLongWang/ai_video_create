# Performance 与 Recovery 验收（2026-10-16）

环境：Windows / Python 3.12.3 / Mock Providers。

| 套件 | 命令 | 结果 |
|---|---|---|
| Performance | `pytest backend/tests/performance/test_benchmarks.py -m performance -q` | 19 passed / 20.48s |
| Recovery | `pytest backend/tests/recovery -q` | 55 passed / 5.93s |

覆盖范围包括 compiler/DAG/调度/API/Worker/内存基准，以及 SQLite 备份恢复、损坏检测、并发备份、磁盘满、资产写入失败、Worker crash/orphan/restart。Python 3.12 的旧式 `get_event_loop()` 测试调用已改为 `asyncio.run()`，warning-as-error 下通过。

详细阈值与复现方法见 [`../benchmarks.md`](../benchmarks.md)，运维流程见 [`../operations/README.md`](../operations/README.md)。
