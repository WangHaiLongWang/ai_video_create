# Phase E: 发布验收

> 2026-09-15
> 状态：Superseded，历史方案。当前发布门禁未通过。后续任务以 `2026-09-15-company-delivery-plan.md` 的 Epic E0、E7 和 CI 门禁为准。

---

## 目标

确保项目达到发布质量：安全、稳定、高性能、跨平台兼容。

---

## 详细任务

### E1: 安全加固与测试

#### 1.1 输入校验

| 文件 | 加固项 |
|------|--------|
| `api/workflows.py` | 校验 workflow spec 大小、节点数上限 |
| `api/agent.py` | 限制 prompt 长度、防止 prompt injection |
| `api/config.py` | 校验 URL 格式、防止 SSRF |
| `services/asset_manager.py` | 路径遍历防护（已部分实现） |

#### 1.2 安全中间件

**文件**: `backend/app/middleware.py` (新建)

```python
class SecurityMiddleware:
    """安全中间件 — 请求限制、头部安全。"""
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - 请求体大小限制 (10MB)
    - 速率限制 (简单内存实现)
```

#### 1.3 测试用例

**文件**: `backend/tests/security/test_input_validation.py`

| 测试 | 说明 |
|------|------|
| XSS in workflow name | 工作流名称包含 `<script>` |
| SQL injection in prompt | 提示词包含 SQL 注入 |
| Path traversal in asset | 资产路径包含 `../../` |
| Oversized payload | 超大请求体拒绝 |
| Invalid JSON | 畸形 JSON 处理 |
| Missing required fields | 缺少必填字段 |
| Enum validation | 无效 provider 类型 |

### E2: 恢复测试

#### 2.1 数据库恢复

**文件**: `backend/tests/recovery/test_db_recovery.py`

| 测试 | 说明 |
|------|------|
| Corrupted DB file | 损坏的数据库文件处理 |
| WAL recovery | WAL 日志恢复 |
| Busy timeout | 并发写入超时处理 |
| Connection recovery | 连接断开后重连 |

#### 2.2 Worker 恢复

**文件**: `backend/tests/recovery/test_worker_recovery.py`

| 测试 | 说明 |
|------|------|
| Orphan task recovery | Worker 崩溃后任务回收 |
| Lease expiration | 租约过期任务重新入队 |
| Heartbeat failure | 心跳失败处理 |
| Concurrent claim | 并发领取同一任务 |

#### 2.3 资产恢复

**文件**: `backend/tests/recovery/test_asset_recovery.py`

| 测试 | 说明 |
|------|------|
| Missing asset file | 引用不存在的资产 |
| Disk full | 磁盘满时的处理 |
| Cleanup after crash | 崩溃后临时文件清理 |

### E3: 性能基准

#### 3.1 基准测试

**文件**: `backend/tests/performance/test_benchmarks.py`

| 测试 | 指标 | 目标 |
|------|------|------|
| Workflow compilation | 编译耗时 | < 100ms (100 节点) |
| Task queue throughput | 入队/秒 | > 1000 tasks/s |
| Concurrent execution | 并发 Worker | 4 Worker 无死锁 |
| API response time | 响应时间 | < 50ms (P95) |
| Memory usage | 内存占用 | < 100MB (空闲) |

#### 3.2 负载测试

**文件**: `backend/tests/performance/test_load.py`

| 场景 | 说明 |
|------|------|
| Large workflow | 50 节点工作流编译+执行 |
| Rapid create/delete | 快速创建删除 100 个工作流 |
| Concurrent executions | 同时执行 10 个工作流 |

### E4: 跨平台验证

#### 4.1 路径处理

**文件**: `backend/tests/cross_platform/test_paths.py`

| 测试 | 说明 |
|------|------|
| Windows paths | `D:\path\to\file` |
| Unix paths | `/path/to/file` |
| Mixed separators | 混合路径分隔符 |
| Unicode paths | 中文/特殊字符路径 |

#### 4.2 平台特定

**文件**: `backend/tests/cross_platform/test_platform.py`

| 测试 | 说明 |
|------|------|
| FFmpeg detection | 不同平台 FFmpeg 发现 |
| SQLite locking | Windows vs Unix 锁行为 |
| Line endings | CRLF vs LF |

### E5: 集成验收

#### 5.1 端到端验收

**文件**: `backend/tests/acceptance/test_e2e.py`

| 场景 | 说明 |
|------|------|
| Full pipeline | 提示词 → 视频（mock 模式） |
| Template workflow | 从模板创建 → 执行 |
| Agent generate + execute | Agent 生成 → 执行 |
| Import/export roundtrip | 导入 → 导出 → 验证一致 |

---

## 实现顺序

1. **E1** 安全加固与测试（优先级最高）
2. **E2** 恢复测试（稳定性保障）
3. **E4** 跨平台验证（兼容性）
4. **E3** 性能基准（性能保障）
5. **E5** 集成验收（最终确认）

---

## 验收标准

- [ ] 所有安全测试通过
- [ ] 恢复测试验证崩溃后可恢复
- [ ] 性能基准达到目标值
- [ ] 跨平台路径处理正确
- [ ] 端到端验收通过
- [ ] 所有现有测试仍然通过
- [ ] 无 TypeScript 错误
