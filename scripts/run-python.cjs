const { existsSync } = require('node:fs')
const { join } = require('node:path')
const { spawnSync } = require('node:child_process')

const root = join(__dirname, '..')
const candidates = process.platform === 'win32'
  ? [join(root, 'backend', '.venv', 'Scripts', 'python.exe'), 'python']
  : [join(root, 'backend', '.venv', 'bin', 'python'), 'python3', 'python']

const executable = candidates.find((candidate) => !candidate.includes(root) || existsSync(candidate))
if (!executable) {
  console.error('未找到 Python。请先创建 backend/.venv 或将 Python 加入 PATH。')
  process.exit(1)
}

const result = spawnSync(executable, process.argv.slice(2), {
  cwd: root,
  env: process.env,
  stdio: 'inherit',
})

if (result.error) {
  console.error(result.error.message)
  process.exit(1)
}
process.exit(result.status ?? 1)
