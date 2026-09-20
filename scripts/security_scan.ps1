<#
.SYNOPSIS
    Security scanner CI script -- scans Python and TypeScript sources for secrets.

.DESCRIPTION
    Uses backend.app.services.security_scanner to detect secrets in:
      - Python files under backend/app
      - TypeScript files under frontend/src
      - Config / env files (.env, .json, .yaml, .toml)

    Exits with code 1 if any critical or error severity findings are found.
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Ensure Python is available
# ---------------------------------------------------------------------------
$python = "python"
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    $python = "python3"
}
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: python not found on PATH" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Run the scanner via a small inline script
# ---------------------------------------------------------------------------
$scannerScript = @"
import sys, os, json
sys.path.insert(0, r"$Root")

from backend.app.services.security_scanner import scan_file, Severity

backend_dir = os.path.join(r"$Root", "backend", "app")
frontend_dir = os.path.join(r"$Root", "frontend", "src")

all_findings = []

# Scan Python files
py_exts = {".py"}
for dirpath, _, filenames in os.walk(backend_dir):
    for fn in filenames:
        if os.path.splitext(fn)[1].lower() in py_exts:
            fp = os.path.join(dirpath, fn)
            all_findings.extend(scan_file(fp))

# Scan TypeScript / JS files
ts_exts = {".ts", ".tsx", ".js", ".jsx"}
for dirpath, _, filenames in os.walk(frontend_dir):
    for fn in filenames:
        if os.path.splitext(fn)[1].lower() in ts_exts:
            fp = os.path.join(dirpath, fn)
            all_findings.extend(scan_file(fp))

# Scan config / env files at project root
cfg_names = {".env", ".env.local", ".env.example"}
for fn in os.listdir(r"$Root"):
    ext = os.path.splitext(fn)[1].lower()
    if fn in cfg_names or ext in {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}:
        fp = os.path.join(r"$Root", fn)
        if os.path.isfile(fp):
            all_findings.extend(scan_file(fp))

# ---- summary ----
by_severity = {}
for f in all_findings:
    by_severity.setdefault(f.severity.value, []).append(f)

total = len(all_findings)
critical = len(by_severity.get("critical", []))
error = len(by_severity.get("error", []))
warning = len(by_severity.get("warning", []))

print("=" * 60)
print(" Security Scan Summary")
print("=" * 60)
print(f"  Total findings : {total}")
print(f"  Critical       : {critical}")
print(f"  Error          : {error}")
print(f"  Warning        : {warning}")
print("=" * 60)

if all_findings:
    print()
    print(f"{'File':<60} {'Line':<6} {'Sev':<10} {'Category'}")
    print("-" * 100)
    for f in sorted(all_findings, key=lambda x: (x.severity.value, x.path, x.line)):
        rel = os.path.relpath(f.path, r"$Root")
        print(f"{rel:<60} {f.line:<6} {f.severity.value:<10} {f.category}")
    print()

if critical > 0 or error > 0:
    print("RESULT: FAIL -- critical or error findings detected.")
    sys.exit(1)
else:
    print("RESULT: PASS -- no critical or error findings.")
    sys.exit(0)
"@

$result = & $python -c $scannerScript 2>&1
$exitCode = $LASTEXITCODE

Write-Host $result

if ($exitCode -ne 0) {
    exit $exitCode
}
