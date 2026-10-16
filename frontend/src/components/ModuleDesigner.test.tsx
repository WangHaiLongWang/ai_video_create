import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import { ModuleDesigner } from './ModuleDesigner'
import type { ModuleDefinition, ConfigSchemaField, ModulePort } from '../schemas/module-definition'

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
const mockAddExtendedPort = vi.fn()
const mockUpdateExtendedPort = vi.fn()
const mockDeleteExtendedPort = vi.fn()
const mockSetPortBinding = vi.fn()

let mockState = {
  isOpen: false,
  moduleId: null as string | null,
  draft: null as ModuleDefinition | null,
  isDirty: false,
  error: null as string | null,
}

let mockConfigFields: ConfigSchemaField[] = []

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
      addExtendedPort: mockAddExtendedPort,
      updateExtendedPort: mockUpdateExtendedPort,
      deleteExtendedPort: mockDeleteExtendedPort,
      setPortBinding: mockSetPortBinding,
    }
    if (typeof args[0] === 'function') {
      return args[0](state)
    }
    return state
  },
  configFieldsToSchema: vi.fn(() => ({})),
  schemaToConfigFields: vi.fn(() => mockConfigFields),
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

const corePorts = {
  inputs: [{ id: 'scene', type: 'scene' as const, required: true, cardinality: 'one' as const, label: 'Scene' }],
  outputs: [{ id: 'image', type: 'image' as const, required: false, cardinality: 'one' as const, label: 'Image' }],
}

function draftWithExtended(binding?: string): ModuleDefinition {
  const extended: ModulePort = {
    id: 'reference_image',
    type: 'image',
    required: false,
    cardinality: 'one',
    label: 'Reference image',
    binding,
  }
  return {
    ...sampleDraft,
    ports: {
      inputs: [...corePorts.inputs, extended],
      outputs: [...corePorts.outputs],
    },
  }
}

function openWith(draft: ModuleDefinition, extra: Partial<typeof mockState> = {}) {
  mockState = {
    isOpen: true,
    moduleId: draft.id,
    draft,
    isDirty: false,
    error: null,
    ...extra,
  }
}

function getDialog() {
  const dialog = document.querySelector('.field-dialog')
  if (!dialog) throw new Error('Port editor dialog not open')
  return within(dialog as HTMLElement)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('ModuleDesigner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfigFields = []
    mockState = {
      isOpen: false,
      moduleId: null,
      draft: null,
      isDirty: false,
      error: null,
    }
  })

  it('renders nothing when not open', () => {
    render(<ModuleDesigner />)
    expect(screen.queryByText('Basic Info')).toBeNull()
  })

  it('renders basic info fields when open', () => {
    openWith(sampleDraft)

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
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    expect(screen.getByText('Execution')).toBeDefined()
    expect(screen.getByText('Base Kind')).toBeDefined()
  })

  it('renders provider policy section', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    expect(screen.getByText('Provider Policy')).toBeDefined()
    expect(screen.getByText('Capability')).toBeDefined()
    expect(screen.getByText('Allowed Providers')).toBeDefined()
    expect(screen.getByText('Locked')).toBeDefined()
  })

  it('renders config schema field list', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    expect(screen.getByText('Config Schema')).toBeDefined()
    expect(screen.getByText('Add Field')).toBeDefined()
  })

  it('renders an editable ports section (no longer read-only)', () => {
    openWith(draftWithExtended('ref_image_url'))

    render(<ModuleDesigner />)

    expect(screen.getByText('Ports')).toBeDefined()
    expect(screen.queryByText('Ports (Read-only)')).toBeNull()
    // Core port is listed with a lock; extended port shows its binding target.
    expect(screen.getByText('scene', { selector: '.md-port-id' })).toBeDefined()
    expect(screen.getByText('reference_image', { selector: '.md-port-id' })).toBeDefined()
    expect(screen.getByText('→ ref_image_url')).toBeDefined()
  })

  it('close button calls closeDesigner when not dirty', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    const cancelBtn = screen.getByText('Cancel')
    fireEvent.click(cancelBtn)

    expect(mockCloseDesigner).toHaveBeenCalled()
  })

  it('close with confirmation when dirty', () => {
    openWith(sampleDraft, { isDirty: true })

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
    openWith(sampleDraft, { isDirty: true })

    render(<ModuleDesigner />)

    const saveBtn = screen.getByText('Save')
    fireEvent.click(saveBtn)

    expect(mockSaveDraft).toHaveBeenCalled()
    await waitFor(() => expect(screen.getByText('Save')).toBeDefined())
  })

  it('publish button calls publishDraft', async () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    const publishBtn = screen.getByText('Publish')
    fireEvent.click(publishBtn)

    expect(mockPublishDraft).toHaveBeenCalled()
    await waitFor(() => expect(screen.getByText('Publish')).toBeDefined())
  })

  it('save button is disabled when not dirty', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    const saveBtn = screen.getByText('Save')
    expect(saveBtn.hasAttribute('disabled')).toBe(true)
  })

  it('add field button triggers addConfigField', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    const addBtn = screen.getByText('Add Field')
    fireEvent.click(addBtn)

    expect(mockAddConfigField).toHaveBeenCalled()
  })

  // -------------------------------------------------------------------------
  // Extended port editing
  // -------------------------------------------------------------------------
  it('adds an extended port through the port editor dialog', () => {
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    fireEvent.click(screen.getByTitle('Add input port'))

    const dialog = getDialog()
    fireEvent.change(dialog.getByPlaceholderText('Display name'), { target: { value: 'Ref Image' } })
    fireEvent.click(dialog.getByText('Save'))

    expect(mockAddExtendedPort).toHaveBeenCalledWith(
      'input',
      expect.objectContaining({
        id: 'ref_image',
        type: 'text',
        required: false,
        cardinality: 'one',
      }),
    )
  })

  it('edits an extended port (including its binding)', () => {
    mockConfigFields = [
      { key: 'ref_image_url', type: 'string', title: 'Reference image URL', required: false },
    ]
    openWith(draftWithExtended(undefined))

    render(<ModuleDesigner />)

    fireEvent.click(screen.getByTitle('Edit port'))

    const dialog = getDialog()
    // ID is locked while editing
    const idInput = dialog.getByPlaceholderText('snake_case_port_id') as HTMLInputElement
    expect(idInput.disabled).toBe(true)

    const bindingSelect = dialog.getByText('Binding (config field)').parentElement?.querySelector('select') as HTMLSelectElement
    expect(bindingSelect).toBeDefined()
    fireEvent.change(bindingSelect, { target: { value: 'ref_image_url' } })
    fireEvent.click(dialog.getByText('Save'))

    expect(mockUpdateExtendedPort).toHaveBeenCalledWith(
      'input',
      'reference_image',
      expect.objectContaining({ id: 'reference_image', binding: 'ref_image_url' }),
    )
  })

  it('deletes an extended port', () => {
    openWith(draftWithExtended('ref_image_url'))

    render(<ModuleDesigner />)

    fireEvent.click(screen.getByTitle('Delete port'))

    expect(mockDeleteExtendedPort).toHaveBeenCalledWith('input', 'reference_image')
  })

  it('populates the binding select from config schema fields', () => {
    mockConfigFields = [
      { key: 'ref_image_url', type: 'string', title: 'Reference image', required: false },
      { key: 'style_preset', type: 'string', title: 'Style', required: false },
    ]
    openWith(sampleDraft)

    render(<ModuleDesigner />)

    fireEvent.click(screen.getByTitle('Add input port'))

    const dialog = getDialog()
    expect(dialog.getByText('— 无 binding —')).toBeDefined()
    expect(dialog.getByText('ref_image_url')).toBeDefined()
    expect(dialog.getByText('style_preset')).toBeDefined()
  })

  it('locks the contract fields when editing a core port', () => {
    openWith(draftWithExtended('ref_image_url'))

    render(<ModuleDesigner />)

    // 'scene' is a core input of textToImage — edit opens a label-only dialog.
    const sceneRow = screen.getByText('scene', { selector: '.md-port-id' }).closest('.md-port-item') as HTMLElement
    fireEvent.click(within(sceneRow).getByTitle('Edit label'))

    const dialog = getDialog()
    const typeSelect = dialog.getByText('Type').parentElement?.querySelector('select') as HTMLSelectElement
    expect(typeSelect.disabled).toBe(true)
    // No binding select for core ports
    expect(dialog.queryByText('Binding (config field)')).toBeNull()
    fireEvent.click(dialog.getByText('Save'))

    expect(mockUpdateExtendedPort).toHaveBeenCalledWith(
      'input',
      'scene',
      expect.objectContaining({ id: 'scene' }),
    )
    // No delete affordance on core rows
    expect(within(sceneRow).queryByTitle('Delete port')).toBeNull()
  })

  // -------------------------------------------------------------------------
  // Publish gating
  // -------------------------------------------------------------------------
  it('blocks publish when an extended port has no binding', () => {
    openWith(draftWithExtended(undefined))

    render(<ModuleDesigner />)

    const publishBtn = screen.getByText('Publish')
    expect(publishBtn.hasAttribute('disabled')).toBe(true)
    // Per-port error is visible on the port row
    expect(screen.getByText(/reference_image.*has no binding/)).toBeDefined()
    // Warning badge marks the port as unbound
    expect(screen.getByText('未绑定')).toBeDefined()
  })

  it('allows publish once the extended port is bound', () => {
    openWith(draftWithExtended('ref_image_url'))

    render(<ModuleDesigner />)

    const publishBtn = screen.getByText('Publish')
    expect(publishBtn.hasAttribute('disabled')).toBe(false)
    expect(screen.queryByText('未绑定')).toBeNull()
    expect(screen.queryByText(/has no binding/)).toBeNull()
  })
})
