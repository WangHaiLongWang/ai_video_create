export interface SceneImagePrompt {
  prompt: string
  negativePrompt?: string
  provider?: string
  model?: string
  size?: string       // e.g. "1280x720"
  seed?: number
  referenceAssetIds?: string[]
}

export interface SceneVideoPrompt {
  prompt: string
  provider?: string
  model?: string
  resolution?: string  // e.g. "480P"
  ratio?: string
  duration?: number
  audio?: boolean
  seed?: number
  firstFrameAssetId?: string | null
}

export interface SceneTransition {
  type: string         // "crossfade" | "cut" | "dissolve" etc.
  duration: number     // seconds
}

export interface SceneEntry {
  sceneId: string
  index: number
  title: string
  narration: string
  durationSeconds: number
  locked: boolean
  image: SceneImagePrompt
  video: SceneVideoPrompt
  transition?: SceneTransition
  metadata?: Record<string, unknown>
}

export interface ScenePromptBundle {
  schemaVersion: "1.0"
  storyboardId: string
  workflowId: string
  executionId: string
  title: string
  globalStyle?: string
  negativePrompt?: string
  scenes: SceneEntry[]
  exportedAt?: string  // ISO timestamp
  source?: 'draft' | 'execution' | 'merged'
}
