"""重试/退避机制测试 — 错误分类、指数退避、重试决策、幂等键。"""

import time
import pytest
from backend.app.db.connection import close_connection, init_db
from backend.app.handlers.contracts import NodeError
from backend.app.engine.retry import (
    ErrorCategory,
    RetryPolicy,
    classify_error,
    should_retry,
    calculate_delay,
    get_retry_after,
    get_default_policy,
)
from backend.app.engine.queue import (
    enqueue_tasks,
    claim_task,
    complete_task,
    fail_task,
    retry_node_task,
    check_idempotency,
    get_retryable_tasks,
    get_task,
    DuplicateRetryError,
)


# ======================================================================
#  Fixtures
# ======================================================================

WORKFLOW_ID = "wf-retry-test"
EXECUTION_ID = "exec-retry-test"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用独立的 SQLite 数据库。"""
    monkeypatch.setattr(
        "backend.app.db.connection._DB_PATH", tmp_path / "test_retry.db"
    )
    close_connection()
    init_db()
    conn = __import__("backend.app.db.connection", fromlist=["get_connection"]).get_connection()
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        (WORKFLOW_ID, "retry-test", "{}"),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        (EXECUTION_ID, WORKFLOW_ID, "{}", "running"),
    )
    conn.commit()
    yield
    close_connection()


# ======================================================================
#  1. 错误分类测试 (10+ cases)
# ======================================================================

class TestClassifyError:
    """错误分类测试。"""

    def test_timeout_is_transient(self):
        error = NodeError(code="TIMEOUT", message="请求超时")
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_network_error_is_transient(self):
        error = NodeError(code="NETWORK_ERROR", message="网络连接失败")
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_rate_limited_is_transient(self):
        error = NodeError(code="RATE_LIMITED", message="请求过多")
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_invalid_parameter_is_permanent(self):
        error = NodeError(code="INVALID_PARAMETER", message="参数错误")
        assert classify_error(error) == ErrorCategory.PERMANENT

    def test_auth_failed_is_permanent(self):
        error = NodeError(code="AUTH_FAILED", message="认证失败")
        assert classify_error(error) == ErrorCategory.PERMANENT

    def test_not_found_is_permanent(self):
        error = NodeError(code="NOT_FOUND", message="资源不存在")
        assert classify_error(error) == ErrorCategory.PERMANENT

    def test_disk_full_is_resource(self):
        error = NodeError(code="DISK_FULL", message="磁盘空间不足")
        assert classify_error(error) == ErrorCategory.RESOURCE

    def test_out_of_memory_is_resource(self):
        error = NodeError(code="OUT_OF_MEMORY", message="内存不足")
        assert classify_error(error) == ErrorCategory.RESOURCE

    def test_external_api_error_is_external(self):
        error = NodeError(code="EXTERNAL_API_ERROR", message="外部 API 错误")
        assert classify_error(error) == ErrorCategory.EXTERNAL

    def test_provider_error_is_external(self):
        error = NodeError(code="PROVIDER_ERROR", message="Provider 错误")
        assert classify_error(error) == ErrorCategory.EXTERNAL

    def test_unknown_code_returns_unknown(self):
        error = NodeError(code="SOME_RANDOM_ERROR", message="未知错误")
        assert classify_error(error) == ErrorCategory.UNKNOWN

    def test_empty_code_returns_unknown(self):
        error = NodeError(code="", message="无错误码")
        assert classify_error(error) == ErrorCategory.UNKNOWN

    def test_retryable_true_with_unknown_code_returns_transient(self):
        """handler 标记 retryable=True 但 code 未知 -> TRANSIENT。"""
        error = NodeError(code="CUSTOM_ERR", message="自定义错误", retryable=True)
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_prefix_match(self):
        """前缀匹配：TIMEOUT_500 应匹配 TIMEOUT。"""
        error = NodeError(code="TIMEOUT_500", message="500 超时")
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_case_insensitive(self):
        """大小写不敏感。"""
        error = NodeError(code="timeout", message="超时")
        assert classify_error(error) == ErrorCategory.TRANSIENT


# ======================================================================
#  2. 退避计算测试
# ======================================================================

class TestCalculateDelay:
    """退避延迟计算测试。"""

    def test_first_attempt_base_delay(self):
        """第 1 次尝试: base_delay * base^0 = 1.0。"""
        policy = RetryPolicy(jitter=False)
        delay = calculate_delay(1, policy)
        assert delay == 1.0

    def test_exponential_growth(self):
        """延迟随 attempt 指数增长。"""
        policy = RetryPolicy(jitter=False)
        delays = [calculate_delay(i, policy) for i in range(1, 5)]
        assert delays == [1.0, 2.0, 4.0, 8.0]

    def test_max_delay_cap(self):
        """延迟不超过 max_delay。"""
        policy = RetryPolicy(max_delay=5.0, jitter=False)
        delay = calculate_delay(10, policy)
        assert delay == 5.0

    def test_jitter_adds_variance(self):
        """抖动使延迟在合理范围内。"""
        policy = RetryPolicy(jitter=True)
        delays = [calculate_delay(1, policy) for _ in range(100)]
        # 所有延迟应 > 0 且 <= base_delay (1.0)
        assert all(0 < d <= 1.0 for d in delays)
        # 不应全部相同
        assert len(set(delays)) > 1

    def test_custom_exponential_base(self):
        """自定义指数底数。"""
        policy = RetryPolicy(exponential_base=3.0, jitter=False)
        delays = [calculate_delay(i, policy) for i in range(1, 4)]
        assert delays == [1.0, 3.0, 9.0]

    def test_default_policy(self):
        """默认策略参数。"""
        policy = get_default_policy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0


# ======================================================================
#  3. 重试决策测试
# ======================================================================

class TestShouldRetry:
    """重试决策测试。"""

    def test_retryable_transient_within_limit(self):
        """可重试的瞬态错误，在限制内 -> 应重试。"""
        error = NodeError(code="TIMEOUT", message="超时")
        policy = RetryPolicy(max_attempts=3)
        assert should_retry(error, 1, policy) is True

    def test_no_retry_when_exhausted(self):
        """超过最大重试次数 -> 不重试。"""
        error = NodeError(code="TIMEOUT", message="超时")
        policy = RetryPolicy(max_attempts=3)
        assert should_retry(error, 3, policy) is False

    def test_no_retry_for_permanent_error(self):
        """永久错误 -> 不重试。"""
        error = NodeError(code="AUTH_FAILED", message="认证失败")
        policy = RetryPolicy(max_attempts=5)
        assert should_retry(error, 1, policy) is False

    def test_retryable_external_error(self):
        """外部服务错误 -> 可重试。"""
        error = NodeError(code="EXTERNAL_API_ERROR", message="外部 API 错误")
        policy = RetryPolicy()
        assert should_retry(error, 1, policy) is True

    def test_retryable_resource_error(self):
        """资源错误 -> 可重试。"""
        error = NodeError(code="DISK_FULL", message="磁盘满")
        policy = RetryPolicy()
        assert should_retry(error, 1, policy) is True

    def test_unknown_error_not_retryable(self):
        """未知错误 -> 不可重试。"""
        error = NodeError(code="RANDOM", message="随机错误")
        policy = RetryPolicy()
        assert should_retry(error, 1, policy) is False

    def test_handler_retryable_overrides_unknown(self):
        """handler 标记 retryable + unknown code -> 可重试。"""
        error = NodeError(code="CUSTOM", message="自定义", retryable=True)
        policy = RetryPolicy()
        assert should_retry(error, 1, policy) is True

    def test_policy_exclude_category(self):
        """从可重试集合中移除 RESOURCE -> RESOURCE 不可重试。"""
        error = NodeError(code="DISK_FULL", message="磁盘满")
        policy = RetryPolicy(retryable_categories={ErrorCategory.TRANSIENT})
        assert should_retry(error, 1, policy) is False

    def test_first_attempt_always_retryable_for_transient(self):
        """瞬态错误第 1 次尝试 -> 总是可重试。"""
        error = NodeError(code="TIMEOUT", message="超时")
        policy = RetryPolicy(max_attempts=3)
        assert should_retry(error, 1, policy) is True

    def test_last_attempt_not_retryable(self):
        """达到 max_attempts 时 -> 不可重试。"""
        error = NodeError(code="TIMEOUT", message="超时")
        policy = RetryPolicy(max_attempts=3)
        assert should_retry(error, 2, policy) is True  # 2 < 3 -> True
        assert should_retry(error, 3, policy) is False  # 3 >= 3 -> False


# ======================================================================
#  4. 429 Retry-After 提取测试
# ======================================================================

class TestGetRetryAfter:
    """429 Retry-After 提取测试。"""

    def test_extract_retry_after_int(self):
        error = NodeError(code="429", message="限流", details={"retry_after": 30})
        assert get_retry_after(error) == 30.0

    def test_extract_retry_after_float(self):
        error = NodeError(code="429", message="限流", details={"retry_after": 12.5})
        assert get_retry_after(error) == 12.5

    def test_extract_retry_after_string(self):
        error = NodeError(code="429", message="限流", details={"retry_after": "45"})
        assert get_retry_after(error) == 45.0

    def test_extract_RetryAfter_header(self):
        error = NodeError(code="429", message="限流", details={"Retry-After": "60"})
        assert get_retry_after(error) == 60.0

    def test_extract_camelcase(self):
        error = NodeError(code="429", message="限流", details={"retryAfter": 10})
        assert get_retry_after(error) == 10.0

    def test_no_retry_after_returns_none(self):
        error = NodeError(code="TIMEOUT", message="超时", details={})
        assert get_retry_after(error) is None

    def test_empty_details_returns_none(self):
        error = NodeError(code="TIMEOUT", message="超时")
        assert get_retry_after(error) is None


# ======================================================================
#  5. 幂等键测试
# ======================================================================

class TestIdempotency:
    """幂等键相关测试。"""

    def test_retry_with_idempotency_key(self):
        """重试时设置幂等键。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        fail_task("t1", "失败了", max_retries=1)

        task = retry_node_task(EXECUTION_ID, "n1", idempotency_key="idem-001")
        assert task["idempotency_key"] == "idem-001"
        assert task["status"] == "pending"

    def test_duplicate_idempotency_key_raises(self):
        """相同幂等键重复重试 -> DuplicateRetryError。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        fail_task("t1", "失败了", max_retries=1)

        # 第一次重试 -> 任务回到 pending 状态
        retry_node_task(EXECUTION_ID, "n1", idempotency_key="idem-002")
        # 此时任务状态为 pending（非 failed），幂等键已设置

        # 相同幂等键再次重试 -> 应该被拒绝（任务已处于非 failed 状态）
        with pytest.raises(DuplicateRetryError):
            retry_node_task(EXECUTION_ID, "n1", idempotency_key="idem-002")

    def test_check_idempotency_found(self):
        """check_idempotency 能找到已设置幂等键的任务。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        fail_task("t1", "失败了", max_retries=1)

        retry_node_task(EXECUTION_ID, "n1", idempotency_key="idem-003")
        result = check_idempotency(EXECUTION_ID, "idem-003")
        assert result is not None
        assert result["id"] == "t1"

    def test_check_idempotency_not_found(self):
        """check_idempotency 找不到不存在的幂等键。"""
        result = check_idempotency(EXECUTION_ID, "nonexistent")
        assert result is None


# ======================================================================
#  6. 单节点重试 API 测试
# ======================================================================

class TestRetryNodeTask:
    """单节点重试函数测试。"""

    def test_retry_failed_node(self):
        """重试失败节点 -> 状态重置为 pending。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        fail_task("t1", "执行失败", max_retries=1)

        task = retry_node_task(EXECUTION_ID, "n1")
        assert task["status"] == "pending"
        assert task["attempt"] == 0

    def test_retry_nonexistent_node(self):
        """重试不存在的节点 -> ValueError。"""
        with pytest.raises(ValueError, match="不存在或状态不是 failed"):
            retry_node_task(EXECUTION_ID, "nonexistent-node")

    def test_retry_non_failed_node(self):
        """重试非 failed 状态的节点 -> ValueError。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        complete_task("t1")

        with pytest.raises(ValueError, match="不存在或状态不是 failed"):
            retry_node_task(EXECUTION_ID, "n1")

    def test_retry_clears_error_and_backoff(self):
        """重试应清除错误信息和退避时间。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        fail_task("t1", "错误信息", max_retries=1)
        # 手动设置 next_retry_at
        from backend.app.db.connection import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET next_retry_at = '2099-01-01T00:00:00' WHERE id = 't1'"
        )
        conn.commit()

        task = retry_node_task(EXECUTION_ID, "n1")
        assert task["next_retry_at"] is None or task["next_retry_at"] == ""
        assert task["error"] == "" or task["error"] is None


# ======================================================================
#  7. 退避调度集成测试: 失败 -> 退避 -> Worker 跳过 -> 重试
# ======================================================================

class TestBackoffIntegration:
    """退避调度集成测试。"""

    def test_failed_task_with_delay_not_claimed_immediately(self):
        """设置退避延迟的任务不应被立即领取。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")

        # 使用 RetryPolicy 使任务进入退避
        policy = RetryPolicy(base_delay=300)  # 5 分钟延迟
        fail_task("t1", NodeError(code="TIMEOUT", message="超时"), policy=policy)

        task = get_task("t1")
        assert task["status"] == "pending"
        assert task["next_retry_at"] is not None

        # claim_task 应该跳过退避中的任务
        claimed = claim_task("worker-2")
        # 如果只有 t1 且它在退避中，应该没有可领取的任务
        if claimed is not None:
            assert claimed["id"] != "t1"

    def test_failed_task_without_delay_claimed_immediately(self):
        """没有退避延迟的任务应该可以立即领取。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")

        # 无 policy 时退避兼容模式，next_retry_at 为 None -> 立即可领取
        fail_task("t1", "普通错误")

        task = get_task("t1")
        assert task["status"] == "pending"
        assert task["next_retry_at"] is None

        claimed = claim_task("worker-2")
        assert claimed is not None
        assert claimed["id"] == "t1"


# ======================================================================
#  8. 集成测试: 失败 -> 退避 -> 重试 -> 成功
# ======================================================================

class TestRetryToSuccess:
    """完整重试流程：失败 -> 重置 -> 重试 -> 成功。"""

    def test_retry_then_succeed(self):
        """节点失败 -> 手动重试 -> 重置为 pending -> 再次执行 -> 成功。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
            {"id": "t2", "node_id": "n2", "kind": "textInput", "label": "输入2",
             "config": {}, "depends_on": []},
        ])

        # 第一次执行 t1 - 用 max_retries=1 使其直接失败（不再重试）
        claim_task("worker-1")
        fail_task("t1", "临时错误", max_retries=1)

        # t1 为 failed 状态，t2 仍为 pending（无依赖，不受影响）
        assert get_task("t1")["status"] == "failed"
        assert get_task("t2")["status"] == "pending"

        # 手动重试 t1 -> 重置为 pending
        retry_node_task(EXECUTION_ID, "n1")
        assert get_task("t1")["status"] == "pending"

        # 再次 claim 并完成 t1
        claim_task("worker-1")
        complete_task("t1")
        assert get_task("t1")["status"] == "completed"

        # t2 现在也可以被领取
        claimed = claim_task("worker-1")
        assert claimed is not None
        assert claimed["id"] == "t2"

    def test_get_retryable_tasks(self):
        """获取所有可重试的任务。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
            {"id": "t2", "node_id": "n2", "kind": "textInput", "label": "输入2",
             "config": {}, "depends_on": []},
        ])

        claim_task("worker-1")
        fail_task("t1", "错误1", max_retries=1)
        claim_task("worker-1")
        complete_task("t2")

        retryable = get_retryable_tasks(EXECUTION_ID)
        assert len(retryable) == 1
        assert retryable[0]["id"] == "t1"
