#!/usr/bin/env bash
# ============================================================
# ai_video_create RC 发布检查脚本 (Linux/macOS)
# 用途：在发布 Release Candidate 前执行全面的项目健康检查
# 用法：chmod +x scripts/release-check.sh && ./scripts/release-check.sh
# ============================================================

set -euo pipefail

# ---- 颜色定义 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ---- 计数器 ----
PASSED=0
FAILED=0
WARNED=0
SKIPPED=0

# ---- 辅助函数 ----
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; PASSED=$((PASSED + 1)); }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; FAILED=$((FAILED + 1)); }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; WARNED=$((WARNED + 1)); }
skip()  { echo -e "${YELLOW}[SKIP]${NC}  $*"; SKIPPED=$((SKIPPED + 1)); }

# 项目根目录
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "=============================================="
echo "  ai_video_create RC 发布检查"
echo "  项目路径: $ROOT"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# 1. 关键文件存在性检查
# ============================================================
info "========== 1/6 关键文件检查 =========="

KEY_FILES=(
    "backend/app/main.py"
    "backend/app/config.py"
    "backend/app/models.py"
    "backend/app/middleware.py"
    "backend/requirements.txt"
    "backend/pyproject.toml"
    "frontend/package.json"
    "frontend/tsconfig.json"
    "frontend/vite.config.ts"
    "frontend/index.html"
    ".env.example"
    ".gitignore"
    "package.json"
    "README.md"
)

for f in "${KEY_FILES[@]}"; do
    if [ -f "$f" ]; then
        pass "关键文件存在: $f"
    else
        fail "关键文件缺失: $f"
    fi
done

# 数据库迁移文件检查
info "---------- 数据库迁移文件 ----------"
MIGRATION_COUNT=$(find backend/app/db/migrations -name '*.sql' 2>/dev/null | wc -l)
if [ "$MIGRATION_COUNT" -ge 6 ]; then
    pass "数据库迁移文件: $MIGRATION_COUNT 个 (>= 6)"
else
    fail "数据库迁移文件不足: 仅 $MIGRATION_COUNT 个 (需要 >= 6)"
fi

# ============================================================
# 2. 依赖完整性检查
# ============================================================
info "========== 2/6 依赖完整性检查 =========="

# Python 虚拟环境
if [ -d "backend/.venv" ]; then
    pass "Python 虚拟环境存在: backend/.venv"
else
    fail "Python 虚拟环境缺失: backend/.venv"
fi

# Python 依赖
PYTHON_BIN=""
if [ -f "backend/.venv/bin/python" ]; then
    PYTHON_BIN="backend/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
fi

if [ -n "$PYTHON_BIN" ]; then
    pass "Python 解释器: $PYTHON_BIN"
    # 检查关键 Python 依赖
    for pkg in fastapi uvicorn pydantic httpx pytest pytest_asyncio; do
        if "$PYTHON_BIN" -c "import $pkg" 2>/dev/null; then
            pass "Python 依赖已安装: $pkg"
        else
            fail "Python 依赖缺失: $pkg"
        fi
    done
else
    fail "未找到 Python 解释器"
fi

# Node.js 依赖
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    pass "Node.js 已安装: $NODE_VERSION"
else
    fail "Node.js 未安装"
fi

if command -v npm &>/dev/null; then
    NPM_VERSION=$(npm --version)
    pass "npm 已安装: $NPM_VERSION"
else
    fail "npm 未安装"
fi

# 前端 node_modules
if [ -d "frontend/node_modules" ]; then
    pass "前端 node_modules 存在"
else
    fail "前端 node_modules 缺失，请先执行 npm install"
fi

# 根目录 node_modules（concurrently 等）
if [ -d "node_modules" ]; then
    pass "根目录 node_modules 存在"
else
    warn "根目录 node_modules 缺失（dev 工具链）"
fi

# ============================================================
# 3. 测试执行检查
# ============================================================
info "========== 3/6 测试检查 =========="

# 后端测试
info "---------- 后端 Pytest ----------"
if [ -n "$PYTHON_BIN" ] && [ -d "backend/.venv" ]; then
    BACKEND_TEST_OUTPUT=$("$PYTHON_BIN" -m pytest backend/tests -v --tb=short 2>&1) || true
    BACKEND_TEST_EXIT=$?

    # 提取测试结果摘要
    BACKEND_SUMMARY=$(echo "$BACKEND_TEST_OUTPUT" | grep -E "passed|failed|error" | tail -1)
    BACKEND_PASSED=$(echo "$BACKEND_SUMMARY" | grep -oP '\d+(?= passed)' || echo "0")
    BACKEND_FAILED=$(echo "$BACKEND_SUMMARY" | grep -oP '\d+(?= failed)' || echo "0")
    BACKEND_SKIPPED=$(echo "$BACKEND_SUMMARY" | grep -oP '\d+(?= skipped)' || echo "0")

    if [ "$BACKEND_FAILED" = "0" ] && [ "$BACKEND_TEST_EXIT" -eq 0 ]; then
        pass "后端测试通过: ${BACKEND_PASSED} passed, ${BACKEND_SKIPPED} skipped"
    else
        fail "后端测试失败: ${BACKEND_FAILED} failed"
    fi
else
    skip "后端测试: Python 环境不完整，跳过"
fi

# 前端测试
info "---------- 前端 Vitest ----------"
if [ -d "frontend/node_modules" ]; then
    FRONTEND_TEST_OUTPUT=$(cd frontend && npx vitest run 2>&1) || true
    FRONTEND_TEST_EXIT=$?

    FRONTEND_PASSED=$(echo "$FRONTEND_TEST_OUTPUT" | grep -oP '\d+(?= passed)' | head -1 || echo "0")
    FRONTEND_FAILED=$(echo "$FRONTEND_TEST_OUTPUT" | grep -oP '\d+(?= failed)' | head -1 || echo "0")

    if [ "${FRONTEND_FAILED:-0}" = "0" ] && [ "$FRONTEND_TEST_EXIT" -eq 0 ]; then
        pass "前端测试通过: ${FRONTEND_PASSED} passed"
    else
        fail "前端测试失败: ${FRONTEND_FAILED} failed"
    fi
else
    skip "前端测试: node_modules 缺失，跳过"
fi

# ============================================================
# 4. TypeScript 类型检查
# ============================================================
info "========== 4/6 TypeScript 类型检查 =========="

if [ -d "frontend/node_modules" ]; then
    TSC_OUTPUT=$(cd frontend && npx tsc --noEmit 2>&1) || true
    TSC_EXIT=$?

    if [ "$TSC_EXIT" -eq 0 ]; then
        pass "TypeScript 类型检查通过"
    else
        fail "TypeScript 类型检查失败"
        echo "$TSC_OUTPUT" | head -20
    fi
else
    skip "TypeScript 类型检查: node_modules 缺失，跳过"
fi

# ============================================================
# 5. 构建检查
# ============================================================
info "========== 5/6 构建检查 =========="

# 后端模块导入检查
info "---------- 后端模块导入检查 ----------"
if [ -n "$PYTHON_BIN" ]; then
    IMPORT_OUTPUT=$("$PYTHON_BIN" -c "from backend.app.main import app; print('FastAPI app loaded successfully')" 2>&1) || true
    if echo "$IMPORT_OUTPUT" | grep -q "loaded successfully"; then
        pass "FastAPI 应用模块可正常导入"
    else
        fail "FastAPI 应用模块导入失败"
        echo "$IMPORT_OUTPUT" | head -10
    fi
fi

# 前端构建
info "---------- 前端 Vite 构建 ----------"
if [ -d "frontend/node_modules" ]; then
    BUILD_OUTPUT=$(cd frontend && npx vite build 2>&1) || true
    BUILD_EXIT=$?

    if [ "$BUILD_EXIT" -eq 0 ]; then
        # 检查 dist 目录是否生成
        if [ -f "frontend/dist/index.html" ]; then
            DIST_SIZE=$(du -sh frontend/dist/ 2>/dev/null | cut -f1)
            pass "前端构建成功: dist/ (${DIST_SIZE})"
        else
            fail "前端构建后 dist/index.html 不存在"
        fi
    else
        fail "前端构建失败"
        echo "$BUILD_OUTPUT" | head -20
    fi
else
    skip "前端构建: node_modules 缺失，跳过"
fi

# ============================================================
# 6. API 可用性快速检查
# ============================================================
info "========== 6/6 API 健康检查 =========="

# 检查是否已有服务器运行
if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    HEALTH_STATUS=$(curl -sf http://127.0.0.1:8000/api/health 2>/dev/null || echo "")
    pass "API 健康检查通过: $HEALTH_STATUS"
else
    skip "API 健康检查: 服务器未运行 (需要先启动 uvicorn)"
fi

# ============================================================
# 结果汇总
# ============================================================
echo ""
echo "=============================================="
echo "  发布检查结果汇总"
echo "=============================================="
echo -e "  ${GREEN}通过:${NC}   $PASSED"
echo -e "  ${RED}失败:${NC}   $FAILED"
echo -e "  ${YELLOW}警告:${NC}   $WARNED"
echo -e "  ${YELLOW}跳过:${NC}   $SKIPPED"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}发布检查未通过！请修复以上 FAIL 项后再发布。${NC}"
    exit 1
elif [ "$WARNED" -gt 0 ]; then
    echo -e "${YELLOW}发布检查通过（有警告）。建议处理以上 WARN 项。${NC}"
    exit 0
else
    echo -e "${GREEN}发布检查全部通过！可以准备 RC 发布。${NC}"
    exit 0
fi
