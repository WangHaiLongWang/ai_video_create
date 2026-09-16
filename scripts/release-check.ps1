# ============================================================
# ai_video_create RC 发布检查脚本 (Windows PowerShell)
# 用途：在发布 Release Candidate 前执行全面的项目健康检查
# 用法：powershell -ExecutionPolicy Bypass -File scripts/release-check.ps1
# ============================================================

$ErrorActionPreference = "Continue"

# ---- 计数器 ----
$script:PASSED = 0
$script:FAILED = 0
$script:WARNED = 0
$script:SKIPPED = 0

# ---- 辅助函数 ----
function Write-Info  { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Cyan }
function Write-Pass  { param([string]$Msg) Write-Host "[PASS]  $Msg" -ForegroundColor Green; $script:PASSED++ }
function Write-Fail  { param([string]$Msg) Write-Host "[FAIL]  $Msg" -ForegroundColor Red; $script:FAILED++ }
function Write-Warn  { param([string]$Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow; $script:WARNED++ }
function Write-Skip  { param([string]$Msg) Write-Host "[SKIP]  $Msg" -ForegroundColor DarkYellow; $script:SKIPPED++ }

# 项目根目录
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host ""
Write-Host "=============================================="
Write-Host "  ai_video_create RC 发布检查"
Write-Host "  项目路径: $Root"
Write-Host "  时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=============================================="
Write-Host ""

# ============================================================
# 1. 关键文件存在性检查
# ============================================================
Write-Info "========== 1/6 关键文件检查 =========="

$KeyFiles = @(
    "backend/app/main.py",
    "backend/app/config.py",
    "backend/app/models.py",
    "backend/app/middleware.py",
    "backend/requirements.txt",
    "backend/pyproject.toml",
    "frontend/package.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "frontend/index.html",
    ".env.example",
    ".gitignore",
    "package.json",
    "README.md"
)

foreach ($f in $KeyFiles) {
    $fullPath = Join-Path $Root $f
    if (Test-Path $fullPath) {
        Write-Pass "关键文件存在: $f"
    } else {
        Write-Fail "关键文件缺失: $f"
    }
}

# 数据库迁移文件检查
Write-Info "---------- 数据库迁移文件 ----------"
$migrationDir = Join-Path $Root "backend/app/db/migrations"
if (Test-Path $migrationDir) {
    $migrationCount = (Get-ChildItem -Path $migrationDir -Filter "*.sql" -ErrorAction SilentlyContinue).Count
    if ($migrationCount -ge 6) {
        Write-Pass "数据库迁移文件: $migrationCount 个 (>= 6)"
    } else {
        Write-Fail "数据库迁移文件不足: 仅 $migrationCount 个 (需要 >= 6)"
    }
} else {
    Write-Fail "数据库迁移目录不存在"
}

# ============================================================
# 2. 依赖完整性检查
# ============================================================
Write-Info "========== 2/6 依赖完整性检查 =========="

# Python 虚拟环境
$venvPath = Join-Path $Root "backend/.venv"
if (Test-Path $venvPath) {
    Write-Pass "Python 虚拟环境存在: backend/.venv"
} else {
    Write-Fail "Python 虚拟环境缺失: backend/.venv"
}

# Python 解释器
$pythonBin = $null
$candidates = @(
    (Join-Path $Root "backend/.venv/Scripts/python.exe"),
    "python",
    "python3"
)

foreach ($c in $candidates) {
    $fullCandidate = if ([System.IO.Path]::IsPathRooted($c)) { $c } else { $c }
    $found = Get-Command $c -ErrorAction SilentlyContinue
    if ($found) {
        # 如果是相对路径的 venv，检查文件是否存在
        if ($c -like "*/backend/.venv/*" -and !(Test-Path $c)) {
            continue
        }
        $pythonBin = $c
        break
    }
}

if ($pythonBin) {
    Write-Pass "Python 解释器: $pythonBin"
    # 检查关键 Python 依赖
    foreach ($pkg in @("fastapi", "uvicorn", "pydantic", "httpx", "pytest", "pytest_asyncio")) {
        $importResult = & $pythonBin -c "import $pkg" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Python 依赖已安装: $pkg"
        } else {
            Write-Fail "Python 依赖缺失: $pkg"
        }
    }
} else {
    Write-Fail "未找到 Python 解释器"
}

# Node.js
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $nodeVersion = & node --version 2>&1
    Write-Pass "Node.js 已安装: $nodeVersion"
} else {
    Write-Fail "Node.js 未安装"
}

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCmd) {
    $npmVersion = & npm --version 2>&1
    Write-Pass "npm 已安装: $npmVersion"
} else {
    Write-Fail "npm 未安装"
}

# 前端 node_modules
$fnmPath = Join-Path $Root "frontend/node_modules"
if (Test-Path $fnmPath) {
    Write-Pass "前端 node_modules 存在"
} else {
    Write-Fail "前端 node_modules 缺失，请先执行 npm install"
}

# 根目录 node_modules
$rootNmPath = Join-Path $Root "node_modules"
if (Test-Path $rootNmPath) {
    Write-Pass "根目录 node_modules 存在"
} else {
    Write-Warn "根目录 node_modules 缺失（dev 工具链）"
}

# ============================================================
# 3. 测试执行检查
# ============================================================
Write-Info "========== 3/6 测试检查 =========="

# 后端测试
Write-Info "---------- 后端 Pytest ----------"
if ($pythonBin -and (Test-Path $venvPath)) {
    $backendTestOutput = & $pythonBin -m pytest backend/tests -v --tb=short 2>&1
    $backendTestExit = $LASTEXITCODE

    # 提取测试结果
    $summaryLine = $backendTestOutput | Select-String -Pattern "passed|failed" | Select-Object -Last 1
    if ($summaryLine) {
        $summaryText = $summaryLine.ToString()
        if ($backendTestExit -eq 0 -or $summaryText -match "0 failed") {
            Write-Pass "后端测试通过: $summaryText"
        } else {
            Write-Fail "后端测试失败: $summaryText"
        }
    } else {
        if ($backendTestExit -eq 0) {
            Write-Pass "后端测试通过（无摘要行）"
        } else {
            Write-Fail "后端测试失败（退出码: $backendTestExit）"
        }
    }
} else {
    Write-Skip "后端测试: Python 环境不完整，跳过"
}

# 前端测试
Write-Info "---------- 前端 Vitest ----------"
if (Test-Path $fnmPath) {
    Push-Location (Join-Path $Root "frontend")
    $frontendTestOutput = & npx vitest run 2>&1
    $frontendTestExit = $LASTEXITCODE
    Pop-Location

    if ($frontendTestExit -eq 0) {
        Write-Pass "前端测试通过"
    } else {
        Write-Fail "前端测试失败"
        $frontendTestOutput | Select-Object -First 20
    }
} else {
    Write-Skip "前端测试: node_modules 缺失，跳过"
}

# ============================================================
# 4. TypeScript 类型检查
# ============================================================
Write-Info "========== 4/6 TypeScript 类型检查 =========="

if (Test-Path $fnmPath) {
    Push-Location (Join-Path $Root "frontend")
    $tscOutput = & npx tsc --noEmit 2>&1
    $tscExit = $LASTEXITCODE
    Pop-Location

    if ($tscExit -eq 0) {
        Write-Pass "TypeScript 类型检查通过"
    } else {
        Write-Fail "TypeScript 类型检查失败"
        $tscOutput | Select-Object -First 20
    }
} else {
    Write-Skip "TypeScript 类型检查: node_modules 缺失，跳过"
}

# ============================================================
# 5. 构建检查
# ============================================================
Write-Info "========== 5/6 构建检查 =========="

# 后端模块导入检查
Write-Info "---------- 后端模块导入检查 ----------"
if ($pythonBin) {
    $importOutput = & $pythonBin -c "from backend.app.main import app; print('FastAPI app loaded successfully')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "FastAPI 应用模块可正常导入"
    } else {
        Write-Fail "FastAPI 应用模块导入失败"
        $importOutput | Select-Object -First 10
    }
}

# 前端构建
Write-Info "---------- 前端 Vite 构建 ----------"
if (Test-Path $fnmPath) {
    Push-Location (Join-Path $Root "frontend")
    $buildOutput = & npx vite build 2>&1
    $buildExit = $LASTEXITCODE
    Pop-Location

    if ($buildExit -eq 0) {
        $distIndex = Join-Path $Root "frontend/dist/index.html"
        if (Test-Path $distIndex) {
            $distSize = (Get-ChildItem -Path (Join-Path $Root "frontend/dist") -Recurse | Measure-Object -Property Length -Sum).Sum
            $distSizeKB = [math]::Round($distSize / 1024)
            Write-Pass "前端构建成功: dist/ (${distSizeKB} KB)"
        } else {
            Write-Fail "前端构建后 dist/index.html 不存在"
        }
    } else {
        Write-Fail "前端构建失败"
        $buildOutput | Select-Object -First 20
    }
} else {
    Write-Skip "前端构建: node_modules 缺失，跳过"
}

# ============================================================
# 6. API 可用性快速检查
# ============================================================
Write-Info "========== 6/6 API 健康检查 =========="

try {
    $healthResponse = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($healthResponse.StatusCode -eq 200) {
        Write-Pass "API 健康检查通过: $($healthResponse.Content)"
    } else {
        Write-Fail "API 健康检查异常: HTTP $($healthResponse.StatusCode)"
    }
} catch {
    Write-Skip "API 健康检查: 服务器未运行 (需要先启动 uvicorn)"
}

# ============================================================
# 结果汇总
# ============================================================
Write-Host ""
Write-Host "=============================================="
Write-Host "  发布检查结果汇总"
Write-Host "=============================================="
Write-Host "  通过:   $script:PASSED" -ForegroundColor Green
Write-Host "  失败:   $script:FAILED" -ForegroundColor Red
Write-Host "  警告:   $script:WARNED" -ForegroundColor Yellow
Write-Host "  跳过:   $script:SKIPPED" -ForegroundColor DarkYellow
Write-Host ""

if ($script:FAILED -gt 0) {
    Write-Host "发布检查未通过！请修复以上 FAIL 项后再发布。" -ForegroundColor Red
    exit 1
} elseif ($script:WARNED -gt 0) {
    Write-Host "发布检查通过（有警告）。建议处理以上 WARN 项。" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "发布检查全部通过！可以准备 RC 发布。" -ForegroundColor Green
    exit 0
}
