import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PropertyPanel } from './PropertyPanel'
import type { StudioNode, FieldDefinition } from '../types'

// ---------------------------------------------------------------------------
// Mock stores
// ---------------------------------------------------------------------------

const mockNodes: StudioNode[] = [
  {
    id: 'n1',
    type: 'studio',
    position: { x: 0, y: 0 },
    data: {
      label: 'Test Node',
      description: 'A test node',
      kind: 'textInput',
      status: 'idle',
      config: {},
      ports: {
        inputs: [],
        outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
      },
    },
  },
]

let selectedNodeId: string | null = null

const mockAddField = vi.fn()
const mockUpdateField = vi.fn()
const mockRemoveField = vi.fn()
const mockDeleteField = vi.fn()
const mockReorderFields = vi.fn()
const mockDuplicateField = vi.fn()
const mockUpdateConfig = vi.fn()
const mockUpdateFieldConfig = vi.fn()

vi.mock('../store', () => ({
  useStudioStore: (...args: unknown[]) => {
    const state = {
      workflow: { nodes: mockNodes, edges: [], id: 'test', name: 'Test', schemaVersion: '2.0' },
      selectedNodeId,
      updateConfig: mockUpdateConfig,
      addField: mockAddField,
      updateField: mockUpdateField,
      removeField: mockRemoveField,
      deleteField: mockDeleteField,
      reorderFields: mockReorderFields,
      duplicateField: mockDuplicateField,
      updateFieldConfig: mockUpdateFieldConfig,
    }
    if (typeof args[0] === 'function') {
      return args[0](state)
    }
    return state
  },
}))

vi.mock('../stores/executionStore', () => ({
  useExecutionStore: (...args: unknown[]) => {
    const state = { status: 'idle' }
    if (typeof args[0] === 'function') {
      return args[0](state)
    }
    return state
  },
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PropertyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    selectedNodeId = null
  })

  it('renders empty state when no node is selected', () => {
    render(<PropertyPanel />)
    expect(screen.getByText('选择一个节点')).toBeDefined()
  })

  it('renders field values for selected node', () => {
    const nodeWithField: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: 'A test node',
        kind: 'textInput',
        status: 'idle',
        config: { my_field: 'hello' },
        fieldSchema: [
          { id: 'my_field', label: 'My Field', type: 'text' },
        ],
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    }

    mockNodes.length = 0
    mockNodes.push(nodeWithField)
    selectedNodeId = 'n1'

    render(<PropertyPanel />)
    expect(screen.getByText('My Field')).toBeDefined()
    expect(screen.getByDisplayValue('hello')).toBeDefined()
  })

  it('add field button triggers dialog', () => {
    mockNodes.length = 0
    mockNodes.push({
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: '',
        kind: 'textInput',
        status: 'idle',
        config: {},
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    })
    selectedNodeId = 'n1'

    render(<PropertyPanel />)
    const addBtn = screen.getByText('添加字段')
    fireEvent.click(addBtn)

    // FieldEditorDialog should appear
    expect(screen.getByText('添加字段', { selector: 'h3' })).toBeDefined()
  })

  it('delete field shows confirmation dialog with config value and irreversibility warning', () => {
    const nodeWithField: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: '',
        kind: 'textInput',
        status: 'idle',
        config: { del_field: 'val_to_show' },
        fieldSchema: [
          { id: 'del_field', label: 'Delete Me', type: 'text' },
        ],
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    }
    mockNodes.length = 0
    mockNodes.push(nodeWithField)
    selectedNodeId = 'n1'

    render(<PropertyPanel />)

    // Click the trash/delete button for the field
    const deleteBtn = screen.getByTitle('删除')
    fireEvent.click(deleteBtn)

    // Confirmation dialog should appear with field name
    expect(screen.getByText('确认删除')).toBeDefined()
    expect(screen.getByText(/确定要删除字段 'Delete Me'/)).toBeDefined()
    // Should show the config value that will be removed
    expect(screen.getByText(/配置值 "val_to_show" 将被移除/)).toBeDefined()
    // Should show irreversibility warning
    expect(screen.getByText(/此操作不可恢复/)).toBeDefined()
  })

  it('reorder fields moves field up/down', () => {
    const nodeWithFields: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: '',
        kind: 'textInput',
        status: 'idle',
        config: {},
        fieldSchema: [
          { id: 'field_a', label: 'Field A', type: 'text' },
          { id: 'field_b', label: 'Field B', type: 'text' },
        ],
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    }
    mockNodes.length = 0
    mockNodes.push(nodeWithFields)
    selectedNodeId = 'n1'

    render(<PropertyPanel />)

    // Second field's "down" arrow should move it from index 1 to index 2 (but it's last so disabled)
    // First field's "down" arrow should move it from index 0 to index 1
    const downButtons = screen.getAllByTitle('下移')
    fireEvent.click(downButtons[0])

    expect(mockReorderFields).toHaveBeenCalledWith('n1', 0, 1)
  })

  it('duplicate field creates copy', () => {
    const nodeWithField: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: '',
        kind: 'textInput',
        status: 'idle',
        config: {},
        fieldSchema: [
          { id: 'orig_field', label: 'Original', type: 'text' },
        ],
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    }
    mockNodes.length = 0
    mockNodes.push(nodeWithField)
    selectedNodeId = 'n1'

    render(<PropertyPanel />)

    const copyBtn = screen.getByTitle('复制')
    fireEvent.click(copyBtn)

    expect(mockDuplicateField).toHaveBeenCalledWith('n1', 'orig_field')
  })

  it('PortEditor renders input/output ports', () => {
    const nodeWithPorts: StudioNode = {
      id: 'n1',
      type: 'studio',
      position: { x: 0, y: 0 },
      data: {
        label: 'Test Node',
        description: '',
        kind: 'textInput',
        status: 'idle',
        config: {},
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one' }],
        },
      },
    }
    mockNodes.length = 0
    mockNodes.push(nodeWithPorts)
    selectedNodeId = 'n1'

    render(<PropertyPanel />)

    // PortEditor should show port section headers
    expect(screen.getByText('输入端口 (0)')).toBeDefined()
    expect(screen.getByText('输出端口 (1)')).toBeDefined()
    expect(screen.getByText('无输入端口')).toBeDefined()
  })
})
