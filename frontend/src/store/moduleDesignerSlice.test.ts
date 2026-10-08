import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useModuleDesignerStore } from './moduleDesignerSlice'
import { createModule, updateModule, publishModule, ModuleApiError } from '../api/modules'
import type { ModuleDefinition, ModulePort } from '../schemas/module-definition'

vi.mock('../api/modules', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/modules')>()
  return {
    ...actual,
    createModule: vi.fn(),
    updateModule: vi.fn(),
    publishModule: vi.fn(),
  }
})

const definition: ModuleDefinition = {
  id: 'custom.image',
  version: '0.1.0',
  status: 'draft',
  baseKind: 'textToImage',
  category: 'Image',
  label: 'Image module',
  providerPolicy: { capability: 'image', allowed: [], locked: false },
  ports: {
    inputs: [{ id: 'scene', type: 'scene', required: true, cardinality: 'one' }],
    outputs: [{ id: 'image', type: 'image', required: false, cardinality: 'one' }],
  },
}

describe('moduleDesignerSlice', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useModuleDesignerStore.getState().closeDesigner()
  })

  it('creates a new draft once, then updates with optimistic locking', async () => {
    vi.mocked(createModule).mockResolvedValue(definition)
    vi.mocked(updateModule).mockResolvedValue(definition)
    const store = useModuleDesignerStore.getState()
    store.openDesigner()
    store.updateDraft({ id: definition.id, label: definition.label })

    await useModuleDesignerStore.getState().saveDraft()
    expect(createModule).toHaveBeenCalledOnce()
    expect(useModuleDesignerStore.getState().moduleId).toBe(definition.id)

    useModuleDesignerStore.getState().updateDraft({ description: 'changed' })
    await useModuleDesignerStore.getState().saveDraft()
    expect(updateModule).toHaveBeenCalledWith(expect.objectContaining({ description: 'changed' }), 1)
    expect(useModuleDesignerStore.getState().expectedVersion).toBe(2)
  })

  it('refreshes core ports when base kind changes', () => {
    useModuleDesignerStore.getState().openDesigner(undefined, definition)
    useModuleDesignerStore.getState().updateDraft({ baseKind: 'imageToVideo' })

    const draft = useModuleDesignerStore.getState().draft
    expect(draft?.ports.inputs[0]?.type).toBe('image')
    expect(draft?.ports.outputs[0]?.type).toBe('video')
  })

  it('preserves extended ports when base kind changes', () => {
    const extended: ModulePort = {
      id: 'reference_image',
      type: 'image',
      required: false,
      cardinality: 'one',
      binding: 'ref_image_url',
    }
    useModuleDesignerStore.getState().openDesigner(undefined, {
      ...definition,
      ports: {
        inputs: [
          { id: 'scene', type: 'scene', required: true, cardinality: 'one' },
          extended,
        ],
        outputs: [{ id: 'image', type: 'image', required: false, cardinality: 'one' }],
      },
    })
    useModuleDesignerStore.getState().updateDraft({ baseKind: 'imageToVideo' })

    const draft = useModuleDesignerStore.getState().draft
    // Core ports refreshed from the new baseKind (imageToVideo: image + scene inputs).
    expect(draft?.ports.inputs.map((p) => p.id)).toEqual(['image', 'scene', 'reference_image'])
    expect(draft?.ports.outputs.map((p) => p.id)).toEqual(['video'])
    // Extended port (and its binding) survives the switch.
    const kept = draft?.ports.inputs.find((p) => p.id === 'reference_image')
    expect(kept?.binding).toBe('ref_image_url')
    expect(kept?.type).toBe('image')
  })

  it('lets the new core contract win when an extended id collides', () => {
    // 'video' is an extension on textToImage but a core output of imageToVideo.
    const colliding: ModulePort = {
      id: 'video',
      type: 'text',          // wrong type vs the new core contract
      required: true,
      cardinality: 'many',
    }
    useModuleDesignerStore.getState().openDesigner(undefined, {
      ...definition,
      ports: {
        inputs: [{ id: 'scene', type: 'scene', required: true, cardinality: 'one' }],
        outputs: [
          { id: 'image', type: 'image', required: false, cardinality: 'one' },
          colliding,
        ],
      },
    })
    useModuleDesignerStore.getState().updateDraft({ baseKind: 'imageToVideo' })

    const draft = useModuleDesignerStore.getState().draft
    // The core 'video' port wins over the colliding extended one.
    expect(draft?.ports.outputs.map((p) => p.id)).toEqual(['video'])
    expect(draft?.ports.outputs[0]?.type).toBe('video')
    expect(draft?.ports.outputs[0]?.cardinality).toBe('one')
  })

  it('adds, updates, binds and deletes extended ports', () => {
    useModuleDesignerStore.getState().openDesigner(undefined, definition)
    const extended: ModulePort = {
      id: 'reference_image',
      type: 'image',
      required: false,
      cardinality: 'one',
    }

    useModuleDesignerStore.getState().addExtendedPort('input', extended)
    let draft = useModuleDesignerStore.getState().draft
    expect(draft?.ports.inputs.map((p) => p.id)).toEqual(['scene', 'reference_image'])

    useModuleDesignerStore.getState().updateExtendedPort('input', 'reference_image', {
      ...extended,
      required: true,
      binding: 'ref_image_url',
    })
    draft = useModuleDesignerStore.getState().draft
    const updated = draft?.ports.inputs.find((p) => p.id === 'reference_image')
    expect(updated?.required).toBe(true)
    expect(updated?.binding).toBe('ref_image_url')

    useModuleDesignerStore.getState().setPortBinding('input', 'reference_image', undefined)
    draft = useModuleDesignerStore.getState().draft
    expect(draft?.ports.inputs.find((p) => p.id === 'reference_image')?.binding).toBeUndefined()

    useModuleDesignerStore.getState().setPortBinding('input', 'reference_image', 'ref_image_url')
    useModuleDesignerStore.getState().deleteExtendedPort('input', 'reference_image')
    draft = useModuleDesignerStore.getState().draft
    expect(draft?.ports.inputs.map((p) => p.id)).toEqual(['scene'])
    expect(useModuleDesignerStore.getState().isDirty).toBe(true)
  })

  it('never adds or deletes a port that shadows a core id', () => {
    useModuleDesignerStore.getState().openDesigner(undefined, definition)

    useModuleDesignerStore.getState().addExtendedPort('input', {
      id: 'scene',
      type: 'text',
      required: false,
      cardinality: 'one',
    })
    useModuleDesignerStore.getState().deleteExtendedPort('input', 'scene')

    const draft = useModuleDesignerStore.getState().draft
    expect(draft?.ports.inputs.map((p) => p.id)).toEqual(['scene'])
    expect(draft?.ports.inputs[0]?.type).toBe('scene')
  })

  it('only applies label changes when updating a core port', () => {
    useModuleDesignerStore.getState().openDesigner(undefined, definition)

    useModuleDesignerStore.getState().updateExtendedPort('input', 'scene', {
      id: 'scene',
      type: 'text',          // locked — must be ignored
      required: false,       // locked — must be ignored
      cardinality: 'many',   // locked — must be ignored
      label: '场景输入',
    })

    const draft = useModuleDesignerStore.getState().draft
    const core = draft?.ports.inputs.find((p) => p.id === 'scene')
    expect(core?.label).toBe('场景输入')
    expect(core?.type).toBe('scene')
    expect(core?.required).toBe(true)
    expect(core?.cardinality).toBe('one')
  })

  it('exposes structured API errors on publish failure', async () => {
    vi.mocked(publishModule).mockRejectedValue(
      new ModuleApiError('UNBOUND_MODULE_PORT: ports.inputs[1].binding - missing', 422, 'MODULE_VALIDATION_FAILED', [
        { field: 'ports.inputs[1].binding', error: 'UNBOUND_MODULE_PORT', message: 'missing' },
      ]),
    )
    useModuleDesignerStore.getState().openDesigner(undefined, definition)

    await expect(useModuleDesignerStore.getState().publishDraft()).rejects.toThrow()
    expect(useModuleDesignerStore.getState().validationErrors).toEqual([
      { field: 'ports.inputs[1].binding', error: 'UNBOUND_MODULE_PORT', message: 'missing' },
    ])
    expect(useModuleDesignerStore.getState().error).toContain('UNBOUND_MODULE_PORT')
  })

  it('uses the persisted optimistic-lock token when reopening a draft', () => {
    useModuleDesignerStore.getState().openDesigner(undefined, {
      ...definition,
      expectedVersion: 7,
    })

    expect(useModuleDesignerStore.getState().expectedVersion).toBe(7)
  })

  it('keeps dirty state and exposes API errors', async () => {
    vi.mocked(updateModule).mockRejectedValue(new Error('optimistic lock conflict'))
    useModuleDesignerStore.getState().openDesigner(undefined, definition)
    useModuleDesignerStore.getState().updateDraft({ description: 'changed' })

    await expect(useModuleDesignerStore.getState().saveDraft()).rejects.toThrow('optimistic lock conflict')
    expect(useModuleDesignerStore.getState().isDirty).toBe(true)
    expect(useModuleDesignerStore.getState().error).toBe('optimistic lock conflict')
  })
})
