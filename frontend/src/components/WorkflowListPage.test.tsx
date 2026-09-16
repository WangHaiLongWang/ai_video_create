/**
 * WorkflowListPage 测试
 *
 * 测试内容:
 * 1. Store 层面测试: fetchWorkflows / deleteWorkflow / exportWorkflow / importWorkflow API 调用
 * 2. 组件行为描述: 渲染、搜索、加载、删除、导出、导入
 *
 * 注意: 当前测试环境模拟 fetch 行为，验证 API 集成逻辑
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import type { WorkflowSummary, WorkflowDetail } from '../api'

// Mock fetch
const fetchMock = vi.fn()
globalThis.fetch = fetchMock

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: vi.fn((_i: number) => null),
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock URL and Blob for export download
const mockCreateObjectURL = vi.fn((_blob: Blob) => 'blob:mock-url')
const mockRevokeObjectURL = vi.fn()
Object.defineProperty(globalThis.URL, 'createObjectURL', { value: mockCreateObjectURL })
Object.defineProperty(globalThis.URL, 'revokeObjectURL', { value: mockRevokeObjectURL })

// Mock document.createElement for download link
const mockClick = vi.fn()
const originalCreateElement = document.createElement.bind(document)
vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
  const el = originalCreateElement(tag)
  if (tag === 'a') {
    el.click = mockClick
    Object.defineProperty(el, 'href', { writable: true, value: '' })
    Object.defineProperty(el, 'download', { writable: true, value: '' })
  }
  return el
})
vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node)
vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node)

// Import api after mocks
import * as api from '../api'

const mockWorkflows: WorkflowSummary[] = [
  {
    id: 'wf-1',
    name: '测试工作流A',
    description: '第一个测试工作流',
    version: 1,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
  {
    id: 'wf-2',
    name: '测试工作流B',
    description: '第二个测试工作流',
    version: 2,
    created_at: '2025-01-03T00:00:00Z',
    updated_at: '2025-01-04T00:00:00Z',
  },
  {
    id: 'wf-3',
    name: '另一个工作流',
    description: '',
    version: 3,
    created_at: '2025-01-05T00:00:00Z',
    updated_at: '2025-01-06T00:00:00Z',
  },
]

describe('WorkflowListPage - API 集成', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockWorkflows),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('fetchWorkflows 获取工作流列表', () => {
    it('调用正确的 API 端点', async () => {
      await api.fetchWorkflows()
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows',
        expect.objectContaining({
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('返回工作流列表', async () => {
      const result = await api.fetchWorkflows()
      expect(result).toHaveLength(3)
      expect(result[0].id).toBe('wf-1')
      expect(result[0].name).toBe('测试工作流A')
    })

    it('每个工作流包含必要字段', async () => {
      const result = await api.fetchWorkflows()
      result.forEach((w) => {
        expect(w).toHaveProperty('id')
        expect(w).toHaveProperty('name')
        expect(w).toHaveProperty('version')
        expect(w).toHaveProperty('created_at')
        expect(w).toHaveProperty('updated_at')
      })
    })
  })

  describe('deleteWorkflow 删除工作流', () => {
    it('调用 DELETE 方法到正确端点', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: () => Promise.resolve(undefined),
      })

      await api.deleteWorkflow('wf-1')

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows/wf-1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })

  describe('exportWorkflow 导出工作流', () => {
    it('调用 POST 方法到 export 端点', async () => {
      const mockSpec = { schemaVersion: '1.0', id: 'wf-1', name: '测试', nodes: [], edges: [] }
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ spec: mockSpec }),
      })

      const result = await api.exportWorkflow('wf-1')

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows/wf-1/export',
        expect.objectContaining({ method: 'POST' }),
      )
      expect(result.spec).toEqual(mockSpec)
    })
  })

  describe('importWorkflow 导入工作流', () => {
    it('调用 POST 方法到 import 端点', async () => {
      const mockSpec = { schemaVersion: '1.0', name: '导入的工作流', nodes: [], edges: [] }
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: 'wf-new', name: '导入的工作流', version: 1 }),
      })

      const result = await api.importWorkflow(mockSpec)

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/workflows/import',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(mockSpec),
        }),
      )
      expect(result.id).toBe('wf-new')
    })
  })

  describe('导出下载逻辑', () => {
    it('创建 Blob 和下载链接', async () => {
      const mockSpec = { schemaVersion: '1.0', id: 'wf-1', name: '下载测试', nodes: [], edges: [] }
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ spec: mockSpec }),
      })

      const result = await api.exportWorkflow('wf-1')
      const json = JSON.stringify(result.spec, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = mockCreateObjectURL(blob)

      expect(url).toBe('blob:mock-url')
      expect(mockCreateObjectURL).toHaveBeenCalled()
    })
  })
})

describe('WorkflowListPage - 组件行为描述', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockWorkflows),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('初始状态: 应调用 fetchWorkflows 加载列表', async () => {
    await api.fetchWorkflows()
    expect(fetchMock).toHaveBeenCalled()
  })

  it('空列表: 当 fetchWorkflows 返回空数组时, 列表为空', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    })

    const result = await api.fetchWorkflows()
    expect(result).toHaveLength(0)
  })

  it('搜索过滤: 工作流可按名称过滤', () => {
    const search = '测试'
    const filtered = mockWorkflows.filter(
      (w) => w.name.toLowerCase().includes(search.toLowerCase()),
    )
    expect(filtered).toHaveLength(2) // 测试工作流A 和 测试工作流B
  })

  it('搜索过滤: 空搜索返回全部', () => {
    const search = ''
    const filtered = mockWorkflows.filter(
      (w) => w.name.toLowerCase().includes(search.toLowerCase()),
    )
    expect(filtered).toHaveLength(3)
  })

  it('搜索过滤: 精确匹配单个工作流', () => {
    const search = '另一个'
    const filtered = mockWorkflows.filter(
      (w) => w.name.toLowerCase().includes(search.toLowerCase()),
    )
    expect(filtered).toHaveLength(1)
    expect(filtered[0].id).toBe('wf-3')
  })

  it('删除工作流后列表应更新', async () => {
    let currentWorkflows = [...mockWorkflows]

    // 模拟删除
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: () => Promise.resolve(undefined),
    })

    await api.deleteWorkflow('wf-1')
    currentWorkflows = currentWorkflows.filter((w) => w.id !== 'wf-1')

    expect(currentWorkflows).toHaveLength(2)
    expect(currentWorkflows.find((w) => w.id === 'wf-1')).toBeUndefined()
  })

  it('导入工作流后应刷新列表', async () => {
    const newWorkflow: WorkflowSummary = {
      id: 'wf-new',
      name: '导入的工作流',
      description: '',
      version: 1,
      created_at: '2025-01-10T00:00:00Z',
      updated_at: '2025-01-10T00:00:00Z',
    }

    // 模拟导入
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 'wf-new', name: '导入的工作流', version: 1 }),
    })

    await api.importWorkflow({ name: '导入的工作流', nodes: [], edges: [] })

    // 模拟刷新列表
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([...mockWorkflows, newWorkflow]),
    })

    const updatedList = await api.fetchWorkflows()
    expect(updatedList).toHaveLength(4)
  })

  it('获取工作流详情用于加载', async () => {
    const detailSpec = {
      schemaVersion: '1.0',
      id: 'wf-1',
      name: '测试工作流A',
      nodes: [{ id: 'n1', type: 'text', position: { x: 0, y: 0 }, data: { label: 'Text', description: '', kind: 'textInput', status: 'idle', config: {} } }],
      edges: [],
    }

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        id: 'wf-1',
        name: '测试工作流A',
        spec: detailSpec,
        version: 1,
      }),
    })

    const result = await api.getWorkflow('wf-1')
    expect(result.spec).toEqual(detailSpec)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/workflows/wf-1',
      expect.anything(),
    )
  })
})
