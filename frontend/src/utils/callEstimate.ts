/**
 * Compute expected API call counts from a WorkflowSpec.
 *
 * Analyses node configs for:
 *   - storyboard node -> scene count (config.scenes)
 *   - textToImage node -> image generation calls (sceneCount * variantCount)
 *   - imageToVideo node -> video generation calls (sceneCount * variantCount)
 *   - videoConcat node -> concat calls
 *   - variant count from any node's config.variantCount or defaults to 1
 *   - video duration from imageToVideo node's config.duration
 */

import type { StudioNode, WorkflowSpec, CallEstimate } from '../types'

interface NodesByKind {
  storyboard: StudioNode | null
  textToImage: StudioNode | null
  imageToVideo: StudioNode | null
  videoConcat: StudioNode | null
}

function groupByKind(nodes: StudioNode[]): NodesByKind {
  const result: NodesByKind = {
    storyboard: null,
    textToImage: null,
    imageToVideo: null,
    videoConcat: null,
  }
  for (const node of nodes) {
    const kind = node.data.kind
    if (kind === 'storyboard' && !result.storyboard) result.storyboard = node
    else if (kind === 'textToImage' && !result.textToImage) result.textToImage = node
    else if (kind === 'imageToVideo' && !result.imageToVideo) result.imageToVideo = node
    else if (kind === 'videoConcat' && !result.videoConcat) result.videoConcat = node
  }
  return result
}

export function computeCallEstimate(spec: WorkflowSpec, overrides?: Partial<Pick<CallEstimate, 'variantCount' | 'videoDuration' | 'imageProvider' | 'videoProvider'>>): CallEstimate {
  const { storyboard, textToImage, imageToVideo, videoConcat } = groupByKind(spec.nodes)

  const sceneCount = Number(storyboard?.data.config.scenes ?? 5)
  const variantCount = overrides?.variantCount
    ?? Number((storyboard?.data.config.variantCount ?? imageToVideo?.data.config.variantCount ?? 1))
  const videoDuration = overrides?.videoDuration
    ?? Number(imageToVideo?.data.config.duration ?? 5)

  const imageCalls = sceneCount * variantCount
  const videoCalls = sceneCount * variantCount
  const storyboardCalls = storyboard ? 1 : 0
  const concatCalls = videoConcat ? 1 : 0
  const totalCalls = storyboardCalls + imageCalls + videoCalls + concatCalls

  const estimatedDurationSeconds = videoCalls * videoDuration

  const imageProvider = overrides?.imageProvider
    ?? (textToImage?.data.config.provider as string ?? '')
  const videoProvider = overrides?.videoProvider
    ?? (imageToVideo?.data.config.provider as string ?? '')

  return {
    sceneCount,
    variantCount,
    videoDuration,
    imageCalls,
    videoCalls,
    storyboardCalls,
    concatCalls,
    totalCalls,
    estimatedDurationSeconds,
    imageProvider,
    videoProvider,
  }
}

/** Apply user overrides to a WorkflowSpec by updating relevant node configs. */
export function applyOverridesToSpec(
  spec: WorkflowSpec,
  overrides: Partial<Pick<CallEstimate, 'variantCount' | 'videoDuration' | 'imageProvider' | 'videoProvider'>>,
): WorkflowSpec {
  const nodes = spec.nodes.map((node) => {
    const newConfig = { ...node.data.config }

    if (node.data.kind === 'storyboard' && overrides.variantCount !== undefined) {
      newConfig.variantCount = overrides.variantCount
    }
    if (node.data.kind === 'imageToVideo') {
      if (overrides.videoDuration !== undefined) newConfig.duration = overrides.videoDuration
      if (overrides.videoProvider !== undefined) newConfig.provider = overrides.videoProvider
    }
    if (node.data.kind === 'textToImage' && overrides.imageProvider !== undefined) {
      newConfig.provider = overrides.imageProvider
    }

    return {
      ...node,
      data: { ...node.data, config: newConfig },
    }
  })

  return { ...spec, nodes }
}
