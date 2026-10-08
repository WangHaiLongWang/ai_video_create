import { afterEach, describe, expect, it, vi } from 'vitest'
import { checkModuleCompat, createModule, fetchModuleDiff, publishModule, updateModule } from './modules'
import { BUILTIN_MODULES } from '../schemas/module-definition'

describe('module API', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('creates a draft with the definition as the request body', async () => {
    const definition = BUILTIN_MODULES[0]
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(definition), { status: 201 }),
    )

    await createModule(definition)

    expect(fetchMock).toHaveBeenCalledWith('/api/modules', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(definition),
    }))
  })

  it('updates a draft through the optimistic-lock route and body', async () => {
    const definition = { ...BUILTIN_MODULES[0], id: 'custom.image', status: 'draft' as const }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(definition), { status: 200 }),
    )

    await updateModule(definition, 3)

    expect(fetchMock).toHaveBeenCalledWith('/api/modules/custom.image/draft', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ definition, expectedVersion: 3 }),
    }))
  })

  it('surfaces backend detail and status on failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'optimistic lock conflict' }), { status: 409 }),
    )

    await expect(updateModule(BUILTIN_MODULES[0], 1)).rejects.toMatchObject({
      message: 'optimistic lock conflict',
      status: 409,
    })
  })

  it('publishes an exact version with its optimistic-lock token', async () => {
    const definition = { ...BUILTIN_MODULES[0], status: 'published' as const, expectedVersion: 5 }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(definition), { status: 200 }),
    )

    await publishModule(definition.id, definition.version, 4)

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/modules/${definition.id}/publish`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ version: definition.version, expectedVersion: 4 }),
      }),
    )
  })
})

describe('module diff / compat API (MOD-201)', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('fetchModuleDiff calls GET /api/modules/{id}/diff with from/to', async () => {
    const mockDiff = {
      versionFrom: '1.0.0',
      versionTo: '1.1.0',
      breaking: false,
      addedFields: [{ key: 'style' }],
      removedFields: [],
      changedFields: [],
      addedPorts: [],
      removedPorts: [],
      changedPorts: [],
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockDiff), { status: 200 }),
    )

    const result = await fetchModuleDiff('core.storyboard', '1.0.0', '1.1.0')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/modules/core.storyboard/diff?from=1.0.0&to=1.1.0',
    )
    expect(result.versionFrom).toBe('1.0.0')
    expect(result.versionTo).toBe('1.1.0')
    expect(result.addedFields).toEqual([{ key: 'style' }])
    expect(result.breaking).toBe(false)
  })

  it('fetchModuleDiff surfaces errors through ModuleApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Module version not found' }), { status: 404 }),
    )

    await expect(fetchModuleDiff('core.storyboard', '0.0.1', '9.9.9')).rejects.toMatchObject({
      message: 'Module version not found',
      status: 404,
    })
  })

  it('checkModuleCompat calls POST /api/modules/{id}/compat-check', async () => {
    const mockResult = { compatible: true, messages: [] }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockResult), { status: 200 }),
    )

    const body = {
      oldConfig: { prompt: 'hello' },
      oldSchema: { type: 'object', properties: { prompt: { type: 'string' } } },
      newSchema: { type: 'object', properties: { prompt: { type: 'string' }, style: { type: 'string' } } },
    }
    const result = await checkModuleCompat('core.textInput', body)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/modules/core.textInput/compat-check',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body),
      }),
    )
    expect(result.compatible).toBe(true)
    expect(result.messages).toEqual([])
  })
})
