import type { ScenePromptBundle, SceneEntry } from './scene-bundle'

export interface SecurityIssue {
  severity: 'error' | 'warning'
  code: string      // "SECRET_KEY", "SIGNED_URL", "ABSOLUTE_PATH", "API_KEY"
  message: string
  sceneId?: string
  field?: string
}

const SECRET_KEY_PATTERNS = [
  { regex: /sk-[A-Za-z0-9]{16,}/, label: 'sk-* secret key' },
  { regex: /api_key\s*[=:]\s*\S+/i, label: 'api_key assignment' },
  { regex: /apikey\s*:\s*\S+/i, label: 'apikey header' },
  { regex: /token\s*:\s*\S+/i, label: 'token header' },
]

const SIGNED_URL_PATTERNS = [
  { regex: /[?&]Signature=[^&]+/, label: 'AWS Signature' },
  { regex: /[?&]X-Amz-Signature=[^&]+/, label: 'AWS Amz Signature' },
  { regex: /[?&]sig=[^&]+/, label: 'sig parameter' },
]

const ABSOLUTE_PATH_PATTERNS = [
  { regex: /[A-Z]:\\[^"'\s,]+/, label: 'Windows path' },
  { regex: /\/(?:home|tmp|var|etc|usr|opt)\/[^"'\s,]+/, label: 'Unix path' },
]

const API_KEY_VAR_PATTERNS = [
  { regex: /\$\{[A-Z_]*API[_-]?KEY[A-Z_]*\}/i, label: '${API_KEY} reference' },
  { regex: /\$[A-Z_]*API[_-]?KEY[A-Z_]*/i, label: '$API_KEY variable' },
  { regex: /process\.env\./, label: 'process.env. reference' },
]

function checkText(
  text: string,
  sceneId: string | undefined,
  field: string,
): SecurityIssue[] {
  const issues: SecurityIssue[] = []

  for (const { regex, label } of SECRET_KEY_PATTERNS) {
    if (regex.test(text)) {
      issues.push({
        severity: 'error',
        code: 'SECRET_KEY',
        message: `Detected potential secret key (${label}) in ${field}`,
        sceneId,
        field,
      })
    }
  }

  for (const { regex, label } of SIGNED_URL_PATTERNS) {
    if (regex.test(text)) {
      issues.push({
        severity: 'error',
        code: 'SIGNED_URL',
        message: `Detected signed URL parameter (${label}) in ${field}`,
        sceneId,
        field,
      })
    }
  }

  for (const { regex, label } of ABSOLUTE_PATH_PATTERNS) {
    if (regex.test(text)) {
      issues.push({
        severity: 'warning',
        code: 'ABSOLUTE_PATH',
        message: `Detected absolute path (${label}) in ${field}`,
        sceneId,
        field,
      })
    }
  }

  for (const { regex, label } of API_KEY_VAR_PATTERNS) {
    if (regex.test(text)) {
      issues.push({
        severity: 'error',
        code: 'API_KEY',
        message: `Detected API key variable reference (${label}) in ${field}`,
        sceneId,
        field,
      })
    }
  }

  return issues
}

function scanScene(scene: SceneEntry): SecurityIssue[] {
  const issues: SecurityIssue[] = []
  const id = scene.sceneId

  // Check narration
  issues.push(...checkText(scene.narration, id, 'narration'))

  // Check image prompt
  issues.push(...checkText(scene.image.prompt, id, 'image.prompt'))
  if (scene.image.negativePrompt) {
    issues.push(...checkText(scene.image.negativePrompt, id, 'image.negativePrompt'))
  }

  // Check video prompt
  issues.push(...checkText(scene.video.prompt, id, 'video.prompt'))

  // Check title
  issues.push(...checkText(scene.title, id, 'title'))

  return issues
}

export function scanBundleSecurity(bundle: ScenePromptBundle): SecurityIssue[] {
  const issues: SecurityIssue[] = []

  // Check global fields
  issues.push(...checkText(bundle.title, undefined, 'bundle.title'))
  if (bundle.globalStyle) {
    issues.push(...checkText(bundle.globalStyle, undefined, 'bundle.globalStyle'))
  }
  if (bundle.negativePrompt) {
    issues.push(...checkText(bundle.negativePrompt, undefined, 'bundle.negativePrompt'))
  }

  // Check each scene
  for (const scene of bundle.scenes) {
    issues.push(...scanScene(scene))
  }

  return issues
}
