import { describe, it, expect } from 'vitest'
import { NODE_CATALOG, NODE_MANIFEST_DOCUMENT } from './node-manifest'
import type { NodeKind } from '../types'

const allKinds: NodeKind[] = [
  'textInput',
  'storyboard',
  'textToImage',
  'imageToVideo',
  'videoConcat',
  'output',
]

/**
 * 前端历史权威表端口契约冻结快照（id / type / required / cardinality）。
 * 与 backend/tests/test_node_catalog.py 的 FRONTEND_PORT_CONTRACT 必须保持同源。
 */
const FRONTEND_PORT_CONTRACT: Record<
  NodeKind,
  { inputs: Array<[string, string, boolean, string]>; outputs: Array<[string, string, boolean, string]> }
> = {
  textInput: {
    inputs: [],
    outputs: [['text', 'text', false, 'one']],
  },
  storyboard: {
    inputs: [['prompt', 'text', true, 'one']],
    outputs: [['scenes', 'scene', false, 'many']],
  },
  textToImage: {
    inputs: [['scene', 'scene', true, 'one']],
    outputs: [['image', 'image', false, 'one']],
  },
  imageToVideo: {
    inputs: [
      ['image', 'image', true, 'one'],
      ['scene', 'scene', false, 'one'],
    ],
    outputs: [['video', 'video', false, 'one']],
  },
  videoConcat: {
    inputs: [['video', 'video', true, 'many']],
    outputs: [['video', 'video', false, 'one']],
  },
  output: {
    inputs: [
      ['video', 'video', false, 'one'],
      ['asset', 'any', false, 'one'],
    ],
    outputs: [],
  },
}

function portTuples(manifest: { ports: { inputs: unknown[]; outputs: unknown[] } }) {
  const side = (ports: unknown[]) =>
    ports.map((p) => {
      const port = p as { id: string; type: string; required: boolean; cardinality: string }
      return [port.id, port.type, port.required, port.cardinality] as [string, string, boolean, string]
    })
  return { inputs: side(manifest.ports.inputs), outputs: side(manifest.ports.outputs) }
}

function rawPortTuples(raw: {
  ports: { inputs: unknown[]; outputs: unknown[] }
}) {
  return portTuples(raw as unknown as { ports: { inputs: unknown[]; outputs: unknown[] } })
}

describe('NODE_CATALOG', () => {
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

  it('output has optional video and generic asset inputs', () => {
    expect(NODE_CATALOG.output.ports.inputs).toHaveLength(2)
    expect(NODE_CATALOG.output.ports.inputs[0].type).toBe('video')
    expect(NODE_CATALOG.output.ports.inputs[1].type).toBe('any')
    expect(NODE_CATALOG.output.ports.inputs.every((port) => !port.required)).toBe(true)
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

describe('HARD-101 shared manifest parity', () => {
  it('test_node_manifest_parity_no_drift', () => {
    // NODE_CATALOG 必须与共享 JSON 逐字段一致
    const rawByKind = new Map(
      NODE_MANIFEST_DOCUMENT.nodeKinds.map((n) => [n.kind, n])
    )
    expect([...rawByKind.keys()].sort()).toEqual([...allKinds].sort())

    for (const kind of allKinds) {
      const catalogEntry = NODE_CATALOG[kind]
      const raw = rawByKind.get(kind)!
      expect(catalogEntry.kind).toBe(raw.kind)
      expect(catalogEntry.version).toBe(raw.version)
      expect(catalogEntry.category).toBe(raw.category)
      expect(catalogEntry.label).toBe(raw.label)
      expect(catalogEntry.description).toBe(raw.description)
      expect(portTuples(catalogEntry)).toEqual(rawPortTuples(raw))
      // 与前端权威表冻结快照一致
      expect(portTuples(catalogEntry)).toEqual(FRONTEND_PORT_CONTRACT[kind])
    }
  })

  it('imageToVideo output cardinality is one (regression)', () => {
    expect(NODE_CATALOG.imageToVideo.ports.outputs[0].cardinality).toBe('one')
  })

  it('textToImage output port id is image (regression)', () => {
    expect(NODE_CATALOG.textToImage.ports.outputs[0].id).toBe('image')
  })

  it('every port has id / type / cardinality / required', () => {
    for (const kind of allKinds) {
      for (const port of [
        ...NODE_CATALOG[kind].ports.inputs,
        ...NODE_CATALOG[kind].ports.outputs,
      ]) {
        expect(port.id.length).toBeGreaterThan(0)
        expect(['text', 'scene', 'image', 'video', 'audio', 'asset', 'any']).toContain(port.type)
        expect(['one', 'many']).toContain(port.cardinality)
        expect(typeof port.required).toBe('boolean')
      }
    }
  })

  it('outputs are never required', () => {
    for (const kind of allKinds) {
      for (const port of NODE_CATALOG[kind].ports.outputs) {
        expect(port.required).toBe(false)
      }
    }
  })

  it('each node exposes a configSchema summary', () => {
    for (const kind of allKinds) {
      expect(NODE_CATALOG[kind].configSchema).toBeDefined()
    }
  })
})
