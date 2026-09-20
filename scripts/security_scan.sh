#!/usr/bin/env bash
# security_scan.sh -- CI security scanner for secrets in source code.
#
# Scans Python files under backend/app, TypeScript files under frontend/src,
# and common config/env files at the project root.
#
# Exits with code 1 if any critical or error findings are detected.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys, os, json
sys.path.insert(0, r'$ROOT_DIR')

from backend.app.services.security_scanner import scan_file, Severity

backend_dir = os.path.join(r'$ROOT_DIR', 'backend', 'app')
frontend_dir = os.path.join(r'$ROOT_DIR', 'frontend', 'src')

all_findings = []

# Scan Python files
for dirpath, _, filenames in os.walk(backend_dir):
    for fn in filenames:
        if fn.endswith('.py'):
            fp = os.path.join(dirpath, fn)
            all_findings.extend(scan_file(fp))

# Scan TypeScript / JS files
for dirpath, _, filenames in os.walk(frontend_dir):
    for fn in filenames:
        if fn.endswith(('.ts', '.tsx', '.js', '.jsx')):
            fp = os.path.join(dirpath, fn)
            all_findings.extend(scan_file(fp))

# Scan config / env files at project root
cfg_names = {'.env', '.env.local', '.env.example'}
for fn in os.listdir(r'$ROOT_DIR'):
    ext = os.path.splitext(fn)[1].lower()
    if fn in cfg_names or ext in ('.json', '.yaml', '.yml', '.toml', '.cfg', '.ini'):
        fp = os.path.join(r'$ROOT_DIR', fn)
        if os.path.isfile(fp):
            all_findings.extend(scan_file(fp))

# ---- summary ----
by_severity = {}
for f in all_findings:
    by_severity.setdefault(f.severity.value, []).append(f)

total = len(all_findings)
critical = len(by_severity.get('critical', []))
error = len(by_severity.get('error', []))
warning = len(by_severity.get('warning', []))

print('=' * 60)
print(' Security Scan Summary')
print('=' * 60)
print(f'  Total findings : {total}')
print(f'  Critical       : {critical}')
print(f'  Error          : {error}')
print(f'  Warning        : {warning}')
print('=' * 60)

if all_findings:
    print()
    print(f'{\"File\":<60} {\"Line\":<6} {\"Sev\":<10} {\"Category\"}')
    print('-' * 100)
    for f in sorted(all_findings, key=lambda x: (x.severity.value, x.path, x.line)):
        rel = os.path.relpath(f.path, r'$ROOT_DIR')
        print(f'{rel:<60} {f.line:<6} {f.severity.value:<10} {f.category}')
    print()

if critical > 0 or error > 0:
    print('RESULT: FAIL -- critical or error findings detected.')
    sys.exit(1)
else:
    print('RESULT: PASS -- no critical or error findings.')
    sys.exit(0)
"
