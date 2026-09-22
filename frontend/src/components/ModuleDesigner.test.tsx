import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ModuleDesigner } from './ModuleDesigner'
import { useModuleDesignerStore } from '../store/moduleDesignerSlice'
import type { ModuleDefinition } from '../schemas/module-definition'

// ---------------------------------------------------------------------------
// Mock store
// ---------------------------------------------------------------------------
const mockOpenDesigner = vi.fn()
const mockUpdateDraft = vi.fn()
const mockSaveDraft = vi.fn()
const mockPublishDraft = vi.fn()
const mockCloseDesigner = vi.fn()
const mockAddConfigField = vi.fn()
const mockUpdateConfigField = vi.fn()
const mockRemoveConfigField = vi.fn()
const mockReorderConfigFields = vi.fn()

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
      updateDraft: mockUpdateDraft,
      saveDraft: mockSaveDraft,
      publishDraft: mockPublishDraft,
      closeDesigner: mockCloseDesigner,
      addConfigField: mockAddConfigField,
      updateConfigField: mockUpdateConfigField,
      removeConfigField: mockRemoveConfigField,
      reorderConfigFields: mockReorderConfigFields,
    }
    if (typeof args[0] === 'function') {
      return args[0](state)
    }
    return state
  },
  configFieldsToSchema: vi.fn(() => ({})),
  schemaToConfigFields: vi.fn(() => []),
}))

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
const sampleDraft: ModuleDefinition = {
  id: 'custom.test-module',
  version: '0.1.0',
  status: 'draft',
  baseKind: 'textToImage',
  category: 'Image',
  label: 'Test Module',
  description: 'A test module',
  icon: 'image-square',
  providerPolicy: {
    capability: 'image',
    allowed: ['doubao'],
    default: 'doubao',
    locked: false,
  },
  configSchema: {
    type: 'object',
    properties: {},
  },
  defaultConfig: {},
  ports: {
    inputs: [],
    outputs: [],
  },
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('ModuleDesigner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState = {
      isOpen: false,
      moduleId: null,
      draft: null,
      isDirty: false,
    }
  })

  it('renders nothing when not open', () => {
    render(<ModuleDesigner />)
    expect(screen.queryByText('Basic Info')).toBeNull()
  })

  it('renders basic info fields when open', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    expect(screen.getByText('Basic Info')).toBeDefined()
    expect(screen.getByText('Module ID')).toBeDefined()
    expect(screen.getByText('Label')).toBeDefined()
    expect(screen.getByText('Description')).toBeDefined()
    expect(screen.getByText('Category')).toBeDefined()
    expect(screen.getByText('Icon')).toBeDefined()
    expect(screen.getByText('Status')).toBeDefined()
  })

  it('renders execution section with baseKind', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    expect(screen.getByText('Execution')).toBeDefined()
    expect(screen.getByText('Base Kind')).toBeDefined()
  })

  it('renders provider policy section', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    expect(screen.getByText('Provider Policy')).toBeDefined()
    expect(screen.getByText('Capability')).toBeDefined()
    expect(screen.getByText('Allowed Providers')).toBeDefined()
    expect(screen.getByText('Locked')).toBeDefined()
  })

  it('renders config schema field list', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    expect(screen.getByText('Config Schema')).toBeDefined()
    expect(screen.getByText('Add Field')).toBeDefined()
  })

  it('renders ports section', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    expect(screen.getByText('Ports (Read-only)')).toBeDefined()
  })

  it('close button calls closeDesigner when not dirty', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    const cancelBtn = screen.getByText('Cancel')
    fireEvent.click(cancelBtn)

    expect(mockCloseDesigner).toHaveBeenCalled()
  })

  it('close with confirmation when dirty', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: true,
    }

    // Mock window.confirm to return false (don't close)
    const originalConfirm = window.confirm
    window.confirm = vi.fn(() => false)

    render(<ModuleDesigner />)

    const cancelBtn = screen.getByText('Cancel')
    fireEvent.click(cancelBtn)

    expect(window.confirm).toHaveBeenCalledWith('You have unsaved changes. Are you sure you want to close?')
    expect(mockCloseDesigner).not.toHaveBeenCalled()

    window.confirm = originalConfirm
  })

  it('save button calls saveDraft', async () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: true,
    }

    render(<ModuleDesigner />)

    const saveBtn = screen.getByText('Save')
    fireEvent.click(saveBtn)

    expect(mockSaveDraft).toHaveBeenCalled()
  })

  it('publish button calls publishDraft', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    const publishBtn = screen.getByText('Publish')
    fireEvent.click(publishBtn)

    expect(mockPublishDraft).toHaveBeenCalled()
  })

  it('save button is disabled when not dirty', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    const saveBtn = screen.getByText('Save')
    expect(saveBtn.hasAttribute('disabled')).toBe(true)
  })

  it('add field button triggers addConfigField', () => {
    mockState = {
      isOpen: true,
      moduleId: null,
      draft: sampleDraft,
      isDirty: false,
    }

    render(<ModuleDesigner />)

    const addBtn = screen.getByText('Add Field')
    fireEvent.click(addBtn)

    expect(mockAddConfigField).toHaveBeenCalled()
  })
})
