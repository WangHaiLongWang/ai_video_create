import { describe, it, expect } from 'vitest'
import { BUILTIN_MODULES, collectPublishBlockers } from './module-definition'
import type { ModuleDefinition, ProviderPolicy, ModulePort } from './module-definition'
import type { PortType } from './node-manifest'

describe('BUILTIN_MODULES', () => {
  it('contains at least the Seedream module', () => {
    const seedream = BUILTIN_MODULES.find((m) => m.id === 'builtin.seedream.text-to-image')
    expect(seedream).toBeDefined()
  })

  it('Seedream module is published', () => {
    const seedream = BUILTIN_MODULES.find((m) => m.id === 'builtin.seedream.text-to-image')!
    expect(seedream.status).toBe('published')
  })

  it('all builtin modules have valid semver versions', () => {
    for (const mod of BUILTIN_MODULES) {
      expect(mod.version).toMatch(/^\d+\.\d+\.\d+$/)
    }
  })
})

describe('ModuleDefinition structure', () => {
  const seedream = BUILTIN_MODULES.find((m) => m.id === 'builtin.seedream.text-to-image')!

  it('has required fields', () => {
    expect(typeof seedream.id).toBe('string')
    expect(seedream.id.length).toBeGreaterThan(0)
    expect(typeof seedream.version).toBe('string')
    expect(typeof seedream.status).toBe('string')
    expect(typeof seedream.baseKind).toBe('string')
    expect(typeof seedream.category).toBe('string')
    expect(typeof seedream.label).toBe('string')
  })

  it('has valid status', () => {
    const validStatuses = ['draft', 'published', 'archived']
    expect(validStatuses).toContain(seedream.status)
  })

  it('has valid baseKind matching NodeKind', () => {
    const validKinds = ['textInput', 'storyboard', 'textToImage', 'imageToVideo', 'videoConcat', 'output']
    expect(validKinds).toContain(seedream.baseKind)
  })

  it('has ports with inputs and outputs', () => {
    expect(seedream.ports).toBeDefined()
    expect(seedream.ports.inputs).toBeDefined()
    expect(seedream.ports.outputs).toBeDefined()
    expect(Array.isArray(seedream.ports.inputs)).toBe(true)
    expect(Array.isArray(seedream.ports.outputs)).toBe(true)
  })
})

describe('ProviderPolicy structure', () => {
  const seedream = BUILTIN_MODULES.find((m) => m.id === 'builtin.seedream.text-to-image')!
  const policy: ProviderPolicy = seedream.providerPolicy

  it('has required fields', () => {
    expect(typeof policy.capability).toBe('string')
    expect(Array.isArray(policy.allowed)).toBe(true)
    expect(policy.allowed.length).toBeGreaterThan(0)
    expect(typeof policy.locked).toBe('boolean')
  })

  it('has valid capability', () => {
    const validCapabilities = ['text', 'image', 'video']
    expect(validCapabilities).toContain(policy.capability)
  })

  it('locked module has a default provider', () => {
    if (policy.locked) {
      expect(policy.default).toBeDefined()
      expect(policy.allowed).toContain(policy.default)
    }
  })

  it('allowed providers are all strings', () => {
    for (const provider of policy.allowed) {
      expect(typeof provider).toBe('string')
      expect(provider.length).toBeGreaterThan(0)
    }
  })
})

describe('ModulePort structure', () => {
  const seedream = BUILTIN_MODULES.find((m) => m.id === 'builtin.seedream.text-to-image')!

  it('input ports have valid structure', () => {
    for (const port of seedream.ports.inputs) {
      expect(typeof port.id).toBe('string')
      expect(port.id.length).toBeGreaterThan(0)
      expect(typeof port.required).toBe('boolean')
      expect(['one', 'many']).toContain(port.cardinality)
    }
  })

  it('output ports have valid structure', () => {
    for (const port of seedream.ports.outputs) {
      expect(typeof port.id).toBe('string')
      expect(port.id.length).toBeGreaterThan(0)
      expect(typeof port.required).toBe('boolean')
      expect(['one', 'many']).toContain(port.cardinality)
    }
  })

  it('port types are valid PortType values', () => {
    const validTypes: PortType[] = ['text', 'scene', 'image', 'video', 'audio', 'asset', 'any']
    const allPorts = [...seedream.ports.inputs, ...seedream.ports.outputs]
    for (const port of allPorts) {
      expect(validTypes).toContain(port.type)
    }
  })

  it('Seedream has scene input and image output', () => {
    const inputIds = seedream.ports.inputs.map((p) => p.id)
    const outputIds = seedream.ports.outputs.map((p) => p.id)
    expect(inputIds).toContain('scene')
    expect(outputIds).toContain('image')
  })
})

describe('BUILTIN_MODULES deduplication', () => {
  it('has no duplicate module IDs', () => {
    const ids = BUILTIN_MODULES.map((m) => m.id)
    const uniqueIds = new Set(ids)
    expect(ids.length).toBe(uniqueIds.size)
  })
})

describe('ModulePort.binding', () => {
  it('round-trips through a serialized ModuleDefinition', () => {
    const port: ModulePort = {
      id: 'reference_image',
      type: 'image',
      required: false,
      cardinality: 'one',
      binding: 'ref_image_url',
    }
    const definition: ModuleDefinition = {
      id: 'custom.ref-module',
      version: '0.1.0',
      status: 'draft',
      baseKind: 'textToImage',
      category: 'Image',
      label: 'Ref module',
      providerPolicy: { capability: 'image', allowed: [], locked: false },
      ports: { inputs: [port], outputs: [] },
    }

    const roundTripped = JSON.parse(JSON.stringify(definition)) as ModuleDefinition
    expect(roundTripped.ports.inputs[0].binding).toBe('ref_image_url')
  })

  it('is optional and survives a definition without bindings', () => {
    const port: ModulePort = { id: 'scene', type: 'scene', required: true, cardinality: 'one' }
    const roundTripped = JSON.parse(JSON.stringify(port)) as ModulePort
    expect(roundTripped.binding).toBeUndefined()
  })
})

describe('collectPublishBlockers', () => {
  const corePort: ModulePort = { id: 'scene', type: 'scene', required: true, cardinality: 'one' }
  const coreOutput: ModulePort = { id: 'image', type: 'image', required: false, cardinality: 'one' }

  it('returns no blockers for a core-only port set', () => {
    const blockers = collectPublishBlockers({ inputs: [corePort], outputs: [coreOutput] }, 'textToImage')
    expect(blockers).toEqual([])
  })

  it('flags an unbound extended port with UNBOUND_MODULE_PORT', () => {
    const extended: ModulePort = {
      id: 'reference_image',
      type: 'image',
      required: false,
      cardinality: 'one',
    }
    const blockers = collectPublishBlockers({ inputs: [corePort, extended], outputs: [coreOutput] }, 'textToImage')
    expect(blockers).toHaveLength(1)
    expect(blockers[0].error).toBe('UNBOUND_MODULE_PORT')
    expect(blockers[0].field).toBe('ports.inputs[1].binding')
    expect(blockers[0].message).toContain('reference_image')
  })

  it('clears the blocker once the extended port has a binding', () => {
    const extended: ModulePort = {
      id: 'reference_image',
      type: 'image',
      required: false,
      cardinality: 'one',
      binding: 'ref_image_url',
    }
    const blockers = collectPublishBlockers({ inputs: [corePort, extended], outputs: [coreOutput] }, 'textToImage')
    expect(blockers).toEqual([])
  })

  it('flags unbound extended outputs too', () => {
    const extendedOut: ModulePort = {
      id: 'debug_preview',
      type: 'image',
      required: false,
      cardinality: 'one',
    }
    const blockers = collectPublishBlockers({ inputs: [corePort], outputs: [coreOutput, extendedOut] }, 'textToImage')
    expect(blockers).toHaveLength(1)
    expect(blockers[0].field).toBe('ports.outputs[1].binding')
  })
})
