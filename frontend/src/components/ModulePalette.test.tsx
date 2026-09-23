import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ModulePalette } from './ModulePalette'
import { useModuleDesignerStore } from '../store/moduleDesignerSlice'
import type { ModuleDefinition } from '../schemas/module-definition'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------
const mockFetchModules = vi.fn()
const mockCloneModule = vi.fn()

vi.mock('../api/modules', () => ({
  fetchModules: (...args: unknown[]) => mockFetchModules(...args),
  cloneModule: (...args: unknown[]) => mockCloneModule(...args),
}))

// ---------------------------------------------------------------------------
// Mock store
// ---------------------------------------------------------------------------
const mockOpenDesigner = vi.fn()

let mockState = {
  isOpen: false,
  moduleId: null as string | null,
  draft: null as ModuleDefinition | null,
  isDirty: false,
}

vi.mock('../store/moduleDesignerSlice', () => ({
  useModuleDesignerStore: (...args: unknown[]) => {
    const state = {
      ...mockState,
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

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
const builtinModule: ModuleDefinition = {
  id: 'builtin.seedream.text-to-image',
  version: '1.0.0',
  status: 'published',
  baseKind: 'textToImage',
  category: 'image',
  label: 'Seedream',
  description: 'Text to image',
  icon: 'image-square',
  providerPolicy: { capability: 'image', allowed: ['doubao'], default: 'doubao', locked: true },
  ports: {
    inputs: [{ id: 'scene', type: 'scene', required: true, cardinality: 'one', label: 'Scene' }],
    outputs: [{ id: 'image', type: 'image', required: false, cardinality: 'one', label: 'Image' }],
  },
  metadata: { builtin: true },
}

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

const llmModule: ModuleDefinition = {
  id: 'builtin.text-llm',
  version: '1.0.0',
  status: 'published',
  baseKind: 'textInput',
  category: 'LLM',
  label: 'Text LLM',
  description: 'Language model',
  icon: 'chat-circle',
  providerPolicy: { capability: 'text', allowed: ['openai'], default: 'openai', locked: false },
  ports: {
    inputs: [{ id: 'prompt', type: 'text', required: true, cardinality: 'one', label: 'Prompt' }],
    outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one', label: 'Text' }],
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('ModulePalette', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState = {
      isOpen: false,
      moduleId: null,
      draft: null,
      isDirty: false,
    }
  })

  it('renders the palette header', () => {
    mockFetchModules.mockResolvedValue([])
    render(<ModulePalette />)
    expect(screen.getByText('模块库')).toBeDefined()
  })

  it('displays loading state', () => {
    mockFetchModules.mockReturnValue(new Promise(() => {})) // never resolves
    render(<ModulePalette />)
    expect(screen.getByText('加载中...')).toBeDefined()
  })

  it('renders category tabs with counts', async () => {
    mockFetchModules.mockResolvedValueOnce([userModule]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    // Wait for data to load
    await screen.findByText('Seedream')

    // Category tabs should be present
    expect(screen.getByText('All')).toBeDefined()
    expect(screen.getByText('Image')).toBeDefined()
    expect(screen.getByText('Video')).toBeDefined()
    expect(screen.getByText('LLM')).toBeDefined()
    expect(screen.getByText('My Modules')).toBeDefined()
  })

  it('filters modules when category tab is clicked', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published (no remote)
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('Seedream')

    // Click Image tab
    fireEvent.click(screen.getByText('Image'))

    // Only image modules should be visible
    expect(screen.getByText('Seedream')).toBeDefined()
    // LLM module should not be visible
    expect(screen.queryByText('Text LLM')).toBeNull()
  })

  it('search filters modules by label', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('Seedream')

    // Type in search
    const searchInput = screen.getByPlaceholderText('搜索模块...')
    fireEvent.change(searchInput, { target: { value: 'Seedream' } })

    // Only matching module should be visible
    expect(screen.getByText('Seedream')).toBeDefined()
  })

  it('search filters modules by description', async () => {
    mockFetchModules.mockResolvedValueOnce([userModule]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('My Video Module')

    const searchInput = screen.getByPlaceholderText('搜索模块...')
    fireEvent.change(searchInput, { target: { value: 'Custom video' } })

    expect(screen.getByText('My Video Module')).toBeDefined()
  })

  it('My Modules shows user-created modules', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([userModule]) // drafts
    render(<ModulePalette />)

    await screen.findByText('My Video Module')

    // Click My Modules tab
    fireEvent.click(screen.getByText('My Modules'))

    // User module should be visible
    expect(screen.getByText('My Video Module')).toBeDefined()
  })

  it('My Modules shows empty hint when no user modules', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('Seedream')

    // Click My Modules tab
    fireEvent.click(screen.getByText('My Modules'))

    expect(screen.getByText('No user-created modules yet')).toBeDefined()
  })

  it('clone button triggers API call', async () => {
    mockFetchModules.mockResolvedValueOnce([userModule]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    mockCloneModule.mockResolvedValue({
      ...userModule,
      id: 'custom.my-video-copy',
      version: '0.1.1',
    })
    render(<ModulePalette />)

    await screen.findByText('My Video Module')

    // Clone button should be visible for user modules
    const cloneBtn = screen.getByText('Clone')
    fireEvent.click(cloneBtn)

    expect(mockCloneModule).toHaveBeenCalledWith('custom.my-video')
  })

  it('module click opens designer', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('Seedream')

    // Click on the module card
    fireEvent.click(screen.getByText('Seedream'))

    expect(mockOpenDesigner).toHaveBeenCalledWith('builtin.seedream.text-to-image', expect.objectContaining({
      id: 'builtin.seedream.text-to-image',
    }))
  })

  it('create button opens designer with no module', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('Seedream')

    // Find and click the create button
    const createBtn = screen.getByTitle('Create new module')
    fireEvent.click(createBtn)

    expect(mockOpenDesigner).toHaveBeenCalledWith()
  })

  it('shows empty message when no modules', async () => {
    mockFetchModules.mockResolvedValueOnce([]) // published
    mockFetchModules.mockResolvedValueOnce([]) // drafts
    render(<ModulePalette />)

    await screen.findByText('暂无可用模块')
    expect(screen.getByText('暂无可用模块')).toBeDefined()
  })
})
