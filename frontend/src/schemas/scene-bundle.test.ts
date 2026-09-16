import { describe, it, expect } from 'vitest'
import type { ScenePromptBundle } from './scene-bundle'
import {
  exportToJson,
  exportToMarkdown,
  exportToCsv,
  exportToText,
  exportToQwenJsonl,
  exportToWan3Jsonl,
} from './scene-export'
import { scanBundleSecurity } from './scene-security'

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

function makeFixture(): ScenePromptBundle {
  return {
    schemaVersion: '1.0',
    storyboardId: 'sb-001',
    workflowId: 'wf-001',
    executionId: 'ex-001',
    title: 'Test Storyboard',
    globalStyle: 'cinematic, warm tones',
    negativePrompt: 'blurry, low quality',
    scenes: [
      {
        sceneId: 's1',
        index: 1,
        title: 'Opening',
        narration: 'The sun rises over the mountains.',
        durationSeconds: 5,
        locked: false,
        image: {
          prompt: 'A sunrise over misty mountains',
          negativePrompt: 'dark',
          model: 'qwen-image-3.0',
          size: '1280x720',
        },
        video: {
          prompt: 'Slow pan across mountain range at dawn',
          model: 'wan3.0-video',
          resolution: '480P',
          ratio: '16:9',
          duration: 5,
        },
      },
      {
        sceneId: 's2',
        index: 2,
        title: 'Journey',
        narration: 'A traveler walks along a winding path.',
        durationSeconds: 8,
        locked: true,
        image: {
          prompt: 'A traveler on a winding forest path',
          model: 'qwen-image-3.0',
          size: '1280x720',
        },
        video: {
          prompt: 'Tracking shot following a traveler through a forest',
          resolution: '720P',
          duration: 8,
        },
      },
    ],
    exportedAt: '2025-01-15T10:00:00Z',
    source: 'draft',
  }
}

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

describe('exportToJson', () => {
  it('returns valid JSON matching the input bundle', () => {
    const bundle = makeFixture()
    const json = exportToJson(bundle)
    const parsed = JSON.parse(json)
    expect(parsed).toEqual(bundle)
  })

  it('preserves schemaVersion', () => {
    const bundle = makeFixture()
    const parsed = JSON.parse(exportToJson(bundle))
    expect(parsed.schemaVersion).toBe('1.0')
  })
})

// ---------------------------------------------------------------------------
// Markdown export
// ---------------------------------------------------------------------------

describe('exportToMarkdown', () => {
  it('contains the bundle title', () => {
    const md = exportToMarkdown(makeFixture())
    expect(md).toContain('# Test Storyboard')
  })

  it('contains scene titles', () => {
    const md = exportToMarkdown(makeFixture())
    expect(md).toContain('## Scene 1: Opening')
    expect(md).toContain('## Scene 2: Journey')
  })

  it('contains image and video prompts', () => {
    const md = exportToMarkdown(makeFixture())
    expect(md).toContain('A sunrise over misty mountains')
    expect(md).toContain('Slow pan across mountain range at dawn')
  })

  it('contains global style and negative prompt', () => {
    const md = exportToMarkdown(makeFixture())
    expect(md).toContain('Global Style: cinematic, warm tones')
    expect(md).toContain('Negative: blurry, low quality')
  })

  it('separates scenes with horizontal rule', () => {
    const md = exportToMarkdown(makeFixture())
    expect(md).toContain('---')
  })
})

// ---------------------------------------------------------------------------
// CSV export
// ---------------------------------------------------------------------------

describe('exportToCsv', () => {
  it('starts with UTF-8 BOM', () => {
    const csv = exportToCsv(makeFixture())
    expect(csv.charCodeAt(0)).toBe(0xFEFF)
  })

  it('has correct header row', () => {
    const csv = exportToCsv(makeFixture())
    const header = csv.split('\n')[0].replace('\ufeff', '')
    expect(header).toBe(
      'sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked'
    )
  })

  it('has one row per scene', () => {
    const csv = exportToCsv(makeFixture())
    const rows = csv.split('\n').filter((r) => r.trim() !== '')
    // header + 2 data rows
    expect(rows.length).toBe(3)
  })

  it('contains scene data', () => {
    const csv = exportToCsv(makeFixture())
    expect(csv).toContain('s1')
    expect(csv).toContain('s2')
    expect(csv).toContain('The sun rises over the mountains.')
  })
})

// ---------------------------------------------------------------------------
// Text export
// ---------------------------------------------------------------------------

describe('exportToText', () => {
  it('contains scene markers', () => {
    const text = exportToText(makeFixture())
    expect(text).toContain('[Scene 1]')
    expect(text).toContain('[Scene 2]')
  })

  it('contains image and video prompts for each scene', () => {
    const text = exportToText(makeFixture())
    expect(text).toContain('Image: A sunrise over misty mountains')
    expect(text).toContain('Video: Slow pan across mountain range at dawn')
    expect(text).toContain('Image: A traveler on a winding forest path')
    expect(text).toContain('Video: Tracking shot following a traveler through a forest')
  })
})

// ---------------------------------------------------------------------------
// Qwen JSONL export
// ---------------------------------------------------------------------------

describe('exportToQwenJsonl', () => {
  it('has one JSON object per scene', () => {
    const jsonl = exportToQwenJsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    expect(lines.length).toBe(2)
  })

  it('each line is valid JSON with required fields', () => {
    const jsonl = exportToQwenJsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    for (const line of lines) {
      const obj = JSON.parse(line)
      expect(obj).toHaveProperty('model')
      expect(obj).toHaveProperty('prompt')
      expect(obj).toHaveProperty('negative_prompt')
      expect(obj).toHaveProperty('size')
    }
  })

  it('uses correct model and size defaults', () => {
    const jsonl = exportToQwenJsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    const obj = JSON.parse(lines[0])
    expect(obj.model).toBe('qwen-image-3.0')
    expect(obj.size).toBe('1280x720')
  })
})

// ---------------------------------------------------------------------------
// Wan3 JSONL export
// ---------------------------------------------------------------------------

describe('exportToWan3Jsonl', () => {
  it('has one JSON object per scene', () => {
    const jsonl = exportToWan3Jsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    expect(lines.length).toBe(2)
  })

  it('each line is valid JSON with required fields', () => {
    const jsonl = exportToWan3Jsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    for (const line of lines) {
      const obj = JSON.parse(line)
      expect(obj).toHaveProperty('model')
      expect(obj).toHaveProperty('prompt')
      expect(obj).toHaveProperty('resolution')
      expect(obj).toHaveProperty('ratio')
      expect(obj).toHaveProperty('duration')
    }
  })

  it('uses correct defaults for missing values', () => {
    const jsonl = exportToWan3Jsonl(makeFixture())
    const lines = jsonl.trim().split('\n')
    // Second scene has resolution "720P" but no ratio, should default
    const obj = JSON.parse(lines[1])
    expect(obj.resolution).toBe('720P')
    expect(obj.ratio).toBe('adaptive')
    expect(obj.model).toBe('wan3.0-video')
  })
})

// ---------------------------------------------------------------------------
// Security scanner
// ---------------------------------------------------------------------------

describe('scanBundleSecurity', () => {
  it('passes a clean bundle with no issues', () => {
    const issues = scanBundleSecurity(makeFixture())
    expect(issues.length).toBe(0)
  })

  it('detects SECRET_KEY patterns (sk-*)', () => {
    const bundle = makeFixture()
    bundle.scenes[0].image.prompt = 'Use key sk-abcdefghijklmnopqrstuvwxyz123456'
    const issues = scanBundleSecurity(bundle)
    const secretIssues = issues.filter((i) => i.code === 'SECRET_KEY')
    expect(secretIssues.length).toBeGreaterThanOrEqual(1)
    expect(secretIssues[0].severity).toBe('error')
    expect(secretIssues[0].sceneId).toBe('s1')
  })

  it('detects api_key= patterns', () => {
    const bundle = makeFixture()
    bundle.scenes[0].narration = 'Set api_key=supersecret123 in the config'
    const issues = scanBundleSecurity(bundle)
    const secretIssues = issues.filter((i) => i.code === 'SECRET_KEY')
    expect(secretIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects signed URL patterns', () => {
    const bundle = makeFixture()
    bundle.scenes[0].image.prompt = 'Load from https://cdn.example.com/img.jpg?X-Amz-Signature=abc123'
    const issues = scanBundleSecurity(bundle)
    const urlIssues = issues.filter((i) => i.code === 'SIGNED_URL')
    expect(urlIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects AWS Signature query param', () => {
    const bundle = makeFixture()
    bundle.scenes[1].video.prompt = 'Fetch https://s3.amazonaws.com/bucket/file?Signature=xyz'
    const issues = scanBundleSecurity(bundle)
    const urlIssues = issues.filter((i) => i.code === 'SIGNED_URL')
    expect(urlIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects absolute paths (Unix)', () => {
    const bundle = makeFixture()
    bundle.scenes[0].image.prompt = 'Load texture from /home/user/assets/texture.png'
    const issues = scanBundleSecurity(bundle)
    const pathIssues = issues.filter((i) => i.code === 'ABSOLUTE_PATH')
    expect(pathIssues.length).toBeGreaterThanOrEqual(1)
    expect(pathIssues[0].severity).toBe('warning')
  })

  it('detects absolute paths (Windows)', () => {
    const bundle = makeFixture()
    bundle.scenes[0].narration = 'Reference C:\\Users\\admin\\file.txt for details'
    const issues = scanBundleSecurity(bundle)
    const pathIssues = issues.filter((i) => i.code === 'ABSOLUTE_PATH')
    expect(pathIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects ${API_KEY} variable references', () => {
    const bundle = makeFixture()
    bundle.scenes[1].video.prompt = 'Send to endpoint with ${API_KEY} header'
    const issues = scanBundleSecurity(bundle)
    const apiKeyIssues = issues.filter((i) => i.code === 'API_KEY')
    expect(apiKeyIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects process.env. references', () => {
    const bundle = makeFixture()
    bundle.scenes[0].image.prompt = 'Use process.env.SECRET_KEY for auth'
    const issues = scanBundleSecurity(bundle)
    const apiKeyIssues = issues.filter((i) => i.code === 'API_KEY')
    expect(apiKeyIssues.length).toBeGreaterThanOrEqual(1)
  })

  it('detects issues in global fields', () => {
    const bundle = makeFixture()
    bundle.globalStyle = 'cinematic with key sk-abcdefghijklmnopqrstuvwxyz123456'
    const issues = scanBundleSecurity(bundle)
    const secretIssues = issues.filter((i) => i.code === 'SECRET_KEY')
    expect(secretIssues.length).toBeGreaterThanOrEqual(1)
    expect(secretIssues[0].sceneId).toBeUndefined()
  })

  it('detects multiple issues in the same bundle', () => {
    const bundle = makeFixture()
    bundle.scenes[0].image.prompt = 'key sk-abcdefghijklmnopqrstuvwxyz123456 path /tmp/file'
    const issues = scanBundleSecurity(bundle)
    const codes = issues.map((i) => i.code)
    expect(codes).toContain('SECRET_KEY')
    expect(codes).toContain('ABSOLUTE_PATH')
  })
})
