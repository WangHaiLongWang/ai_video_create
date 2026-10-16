import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ModulePalette } from './ModulePalette'
import type { ModuleDefinition } from '../schemas/module-definition'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const mockFetchModules = vi.fn()
const mockCloneModule = vi.fn()
const mockOpenDesigner = vi.fn()

vi.mock('../api/modules', () => ({
  fetchModules: (...args: unknown[]) => mockFetchModules(...args),
  cloneModule: (...args: unknown[]) => mockCloneModule(...args),
}))

vi.mock('../store/moduleDesignerSlice', () => ({
  useModuleDesignerStore: (...args: unknown[]) => {
    const state = {
      isOpen: false,
      moduleId: null as string | null,
      draft: null as ModuleDefinition | null,
      isDirty: false,
      openDesigner: mockOpenDesigner,
      updateDraft: vi.fn(),
      saveDraft: vi.fn(),
      publishDraft: vi.fn(),
      closeDesigner: vi.fn(),
      addConfigField: vi.fn(),
      updateConfigField: vi.fn(),
      removeConfigField: vi.fn(),
      reorderConfigFields: vi.fn(),
    }
    if (typeof args[0] === 'function') {
      return args[0](state)
    }
    return state
  },
}))

/** Wait for Seedream builtin to appear after loading */
async function waitForBuiltin(container: HTMLElement) {
  await waitFor(() => {
    expect(container.textContent).toContain('Seedream')
  }, { timeout: 5000 })
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
const userModule: ModuleDefinition = {
  id: 'custom.my-video',
  version: '0.1.0',
  status: 'draft',
  baseKind: 'imageToVideo',
  category: 'Video',
  label: 'My Video Module',
  description: 'Custom video generation',
  icon: 'video',
  providerPolicy: { capability: 'video', allowed: ['kling'], default: 'kling', locked: false },
  ports: {
    inputs: [{ id: 'image', type: 'image', required: true, cardinality: 'one', label: 'Image' }],
    outputs: [{ id: 'video', type: 'video', required: false, cardinality: 'one', label: 'Video' }],
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('ModulePalette', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchModules.mockResolvedValue([])
  })

  it('renders the palette header', async () => {
    const { container } = render(<ModulePalette />)
    expect(screen.getByText('模块库')).toBeDefined()
    await waitForBuiltin(container)
  })

  it('displays loading state', () => {
    mockFetchModules.mockReturnValue(new Promise(() => {}))
    render(<ModulePalette />)
    expect(screen.getByText('加载中...')).toBeDefined()
  })

  it('renders builtin modules after loading', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)
    expect(container.textContent).toContain('Seedream 文生图')
  })

  it('renders category tabs', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    expect(screen.getByText('All')).toBeDefined()
    expect(screen.getByRole('button', { name: /^Image/ })).toBeDefined()
    expect(screen.getByText('Video')).toBeDefined()
    expect(screen.getByText('My Modules')).toBeDefined()
  })

  it('search filters by label', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    const searchInput = screen.getByPlaceholderText('搜索模块...')
    fireEvent.change(searchInput, { target: { value: 'NonexistentXYZ' } })

    expect(container.textContent).not.toContain('Seedream')
  })

  it('search matches partial label', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    const searchInput = screen.getByPlaceholderText('搜索模块...')
    fireEvent.change(searchInput, { target: { value: 'Seedream' } })

    expect(container.textContent).toContain('Seedream')
  })

  it('My Modules shows empty hint when no user modules', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    fireEvent.click(screen.getByText('My Modules'))
    expect(screen.getByText('No user-created modules yet')).toBeDefined()
  })

  it('My Modules shows user-created modules', async () => {
    mockFetchModules.mockResolvedValueOnce([])
    mockFetchModules.mockResolvedValueOnce([userModule])

    const { container } = render(<ModulePalette />)
    await waitFor(() => {
      expect(container.textContent).toContain('My Video Module')
    }, { timeout: 5000 })

    fireEvent.click(screen.getByText('My Modules'))
    expect(screen.getByText('My Video Module')).toBeDefined()
  })

  it('create button opens designer', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    const createBtn = screen.getByTitle('Create new module')
    fireEvent.click(createBtn)

    expect(mockOpenDesigner).toHaveBeenCalledWith()
  })

  it('module click opens designer', async () => {
    const { container } = render(<ModulePalette />)
    await waitForBuiltin(container)

    // Find the module card button containing Seedream
    const cardButtons = container.querySelectorAll('[role="button"].module-card')
    expect(cardButtons.length).toBeGreaterThan(0)
    fireEvent.click(cardButtons[0])

    expect(mockOpenDesigner).toHaveBeenCalledWith(
      'builtin.seedream.text-to-image',
      expect.objectContaining({ id: 'builtin.seedream.text-to-image' }),
    )
  })
})
