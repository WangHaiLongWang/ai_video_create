import { afterEach, describe, expect, it, vi } from 'vitest'
import { createModule, publishModule, updateModule } from './modules'
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
