import type { ScenePromptBundle } from './scene-bundle'

/**
 * Export a ScenePromptBundle to JSON string.
 */
export function exportToJson(bundle: ScenePromptBundle): string {
  return JSON.stringify(bundle, null, 2)
}

/**
 * Export a ScenePromptBundle to Markdown format.
 */
export function exportToMarkdown(bundle: ScenePromptBundle): string {
  const lines: string[] = []
  lines.push(`# ${bundle.title}`)
  lines.push('')

  if (bundle.globalStyle) {
    lines.push(`Global Style: ${bundle.globalStyle}`)
  }
  if (bundle.negativePrompt) {
    lines.push(`Negative: ${bundle.negativePrompt}`)
  }
  if (bundle.globalStyle || bundle.negativePrompt) {
    lines.push('')
  }

  for (let i = 0; i < bundle.scenes.length; i++) {
    const scene = bundle.scenes[i]
    lines.push(`## Scene ${scene.index}: ${scene.title}`)
    lines.push('')
    lines.push(`**Narration:** ${scene.narration}`)
    lines.push(`**Duration:** ${scene.durationSeconds}s`)
    lines.push(`**Image Prompt:** ${scene.image.prompt}`)
    lines.push(`**Video Prompt:** ${scene.video.prompt}`)

    if (i < bundle.scenes.length - 1) {
      lines.push('')
      lines.push('---')
      lines.push('')
    }
  }

  lines.push('')
  return lines.join('\n')
}

/**
 * Export a ScenePromptBundle to CSV format (UTF-8 with BOM).
 */
export function exportToCsv(bundle: ScenePromptBundle): string {
  const BOM = '﻿'
  const header = 'sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked'
  const rows = bundle.scenes.map((scene) => {
    return [
      escapeCsvField(scene.sceneId),
      String(scene.index),
      escapeCsvField(scene.title),
      escapeCsvField(scene.narration),
      String(scene.durationSeconds),
      escapeCsvField(scene.image.prompt),
      escapeCsvField(scene.video.prompt),
      String(scene.locked),
    ].join(',')
  })

  return BOM + header + '\n' + rows.join('\n') + '\n'
}

function escapeCsvField(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return '"' + value.replace(/"/g, '""') + '"'
  }
  return value
}

/**
 * Export a ScenePromptBundle to plain text prompt list.
 */
export function exportToText(bundle: ScenePromptBundle): string {
  const sections: string[] = []

  for (const scene of bundle.scenes) {
    sections.push(`[Scene ${scene.index}]`)
    sections.push(`Image: ${scene.image.prompt}`)
    sections.push(`Video: ${scene.video.prompt}`)
    sections.push('')
  }

  return sections.join('\n')
}

/**
 * Export a ScenePromptBundle to Qwen JSONL format (one image request per line).
 */
export function exportToQwenJsonl(bundle: ScenePromptBundle): string {
  const lines = bundle.scenes.map((scene) => {
    const obj = {
      model: scene.image.model || 'qwen-image-3.0',
      prompt: scene.image.prompt,
      negative_prompt: scene.image.negativePrompt || '',
      size: scene.image.size || '1280x720',
    }
    return JSON.stringify(obj)
  })

  return lines.join('\n') + '\n'
}

/**
 * Export a ScenePromptBundle to Wan3 JSONL format (one video request per line).
 */
export function exportToWan3Jsonl(bundle: ScenePromptBundle): string {
  const lines = bundle.scenes.map((scene) => {
    const obj = {
      model: scene.video.model || 'wan3.0-video',
      prompt: scene.video.prompt,
      resolution: scene.video.resolution || '480P',
      ratio: scene.video.ratio || 'adaptive',
      duration: scene.video.duration || 5,
    }
    return JSON.stringify(obj)
  })

  return lines.join('\n') + '\n'
}
