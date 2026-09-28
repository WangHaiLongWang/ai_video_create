import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useModuleDesignerStore } from './moduleDesignerSlice'
import { createModule, updateModule } from '../api/modules'
import type { ModuleDefinition } from '../schemas/module-definition'

vi.mock('../api/modules', () => ({
  createModule: vi.fn(),
  updateModule: vi.fn(),
  publishModule: vi.fn(),
}))

const definition: ModuleDefinition = {
  id: 'custom.image',
  version: '0.1.0',
  status: 'draft',
  baseKind: 'textToImage',
  category: 'Image',
  label: 'Image module',
  providerPolicy: { capability: 'image', allowed: [], locked: false },
  ports: { inputs: [], outputs: [] },
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
