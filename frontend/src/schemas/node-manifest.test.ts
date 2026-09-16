import { describe, it, expect } from 'vitest'
import { NODE_CATALOG } from './node-manifest'
import type { NodeKind } from '../types'

describe('NODE_CATALOG', () => {
  const allKinds: NodeKind[] = [
    'textInput',
    'storyboard',
    'textToImage',
    'imageToVideo',
    'videoConcat',
    'output',
  ]

  it('contains all 6 node kinds', () => {
    for (const kind of allKinds) {
      expect(NODE_CATALOG[kind]).toBeDefined()
    }
    expect(Object.keys(NODE_CATALOG)).toHaveLength(6)
  })

  it('each manifest has at least one port defined (input or output)', () => {
    for (const kind of allKinds) {
      const manifest = NODE_CATALOG[kind]
      const totalPorts = manifest.ports.inputs.length + manifest.ports.outputs.length
      expect(totalPorts).toBeGreaterThanOrEqual(1)
    }
  })

  it('port IDs are stable strings', () => {
    for (const kind of allKinds) {
      const manifest = NODE_CATALOG[kind]
      for (const port of [...manifest.ports.inputs, ...manifest.ports.outputs]) {
        expect(typeof port.id).toBe('string')
        expect(port.id.length).toBeGreaterThan(0)
        // Port IDs should be simple alphanumeric + underscore
        expect(port.id).toMatch(/^[a-zA-Z_]+$/)
      }
    }
  })

  it('textInput has no inputs', () => {
    expect(NODE_CATALOG.textInput.ports.inputs).toHaveLength(0)
  })

  it('textInput has one text output', () => {
    expect(NODE_CATALOG.textInput.ports.outputs).toHaveLength(1)
    expect(NODE_CATALOG.textInput.ports.outputs[0].type).toBe('text')
  })

  it('output has no outputs', () => {
    expect(NODE_CATALOG.output.ports.outputs).toHaveLength(0)
  })

  it('output has one video input', () => {
    expect(NODE_CATALOG.output.ports.inputs).toHaveLength(1)
    expect(NODE_CATALOG.output.ports.inputs[0].type).toBe('video')
  })

  it('storyboard has prompt input and scenes output', () => {
    const manifest = NODE_CATALOG.storyboard
    expect(manifest.ports.inputs[0].id).toBe('prompt')
    expect(manifest.ports.inputs[0].type).toBe('text')
    expect(manifest.ports.inputs[0].required).toBe(true)
    expect(manifest.ports.outputs[0].id).toBe('scenes')
    expect(manifest.ports.outputs[0].type).toBe('scene')
    expect(manifest.ports.outputs[0].cardinality).toBe('many')
  })

  it('textToImage has mapOver execution hint', () => {
    expect(NODE_CATALOG.textToImage.execution?.mapOver).toBe('scene')
  })

  it('imageToVideo has mapOver execution hint', () => {
    expect(NODE_CATALOG.imageToVideo.execution?.mapOver).toBe('image')
  })

  it('videoConcat accepts many video inputs', () => {
    const manifest = NODE_CATALOG.videoConcat
    const videoInput = manifest.ports.inputs.find((p) => p.id === 'video')
    expect(videoInput).toBeDefined()
    expect(videoInput!.cardinality).toBe('many')
  })

  it('all manifests have valid version strings', () => {
    for (const kind of allKinds) {
      expect(NODE_CATALOG[kind].version).toMatch(/^\d+\.\d+\.\d+$/)
    }
  })

  it('all manifests have valid categories', () => {
    const validCategories = ['input', 'transform', 'video', 'output']
    for (const kind of allKinds) {
      expect(validCategories).toContain(NODE_CATALOG[kind].category)
    }
  })
})
