param([switch]$SkipTests)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$script:Failed = 0
function Pass([string]$Message) { Write-Host "[PASS] $Message" -ForegroundColor Green }
function Fail([string]$Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red; $script:Failed++ }
function Check-Command([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -eq 0) { Pass $Label } else { Fail "$Label (exit $LASTEXITCODE)" }
}
Write-Host "ai_video_create release check - $(Get-Date -Format s)"
$RequiredFiles = @(
    "VERSION", "CHANGELOG.md", ".nvmrc", "package.json", "package-lock.json",
    "backend/requirements.txt", "backend/constraints.txt", "backend/pyproject.toml",
    "frontend/package.json", "frontend/package-lock.json",
    "docs/operations/INSTALL.md", "docs/operations/UPGRADE.md",
    "docs/operations/ROLLBACK.md", "docs/operations/RELEASE-CHECKLIST.md"
)
foreach ($Path in $RequiredFiles) {
    if (Test-Path -LiteralPath (Join-Path $Root $Path)) { Pass "required file: $Path" } else { Fail "missing file: $Path" }
}
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }
Check-Command "canonical release metadata" { & $Python scripts/verify-release-metadata.py }
Check-Command "Python dependency health" { & $Python -m pip check }
Check-Command "Node 22/npm 10 runtime" { & node scripts/check-runtime.cjs }
if (-not $SkipTests) {
    Check-Command "backend non-external tests" { & $Python -m pytest backend/tests -m "not external" -q }
    Check-Command "frontend unit tests" { & npm.cmd --prefix frontend test }
    Check-Command "frontend typecheck" { & npm.cmd --prefix frontend run typecheck }
    Check-Command "frontend production build" { & npm.cmd --prefix frontend run build }
}
Check-Command "release manifest" { & $Python scripts/release-manifest.py --output dist/release-manifest.json }
if ($script:Failed -gt 0) { Write-Host "Release check failed: $script:Failed gate(s)." -ForegroundColor Red; exit 1 }
Pass "all selected local release gates"
exit 0
