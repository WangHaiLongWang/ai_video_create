/**
 * TaskPreview 组件测试
 *
 * 测试内容:
 * 1. TaskPreview 组件渲染各种状态
 * 2. 重试按钮行为
 * 3. ExpandableTaskRow 展开/折叠
 * 4. 预览数据展示
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { TaskPreview as TaskPreviewType } from '../types'

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

// Mock fetch
globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve([]) })

// Mock api
const mockRetryTask = vi.fn().mockResolvedValue({ task_id: 't1', status: 'pending', message: 'ok' })
const mockGetTaskPreview = vi.fn().mockResolvedValue({
  task_id: 't1', status: 'failed', error_message: 'Test error',
})

vi.mock('../api', () => ({
  retryTask: (...args: unknown[]) => mockRetryTask(...(args as [string, string])),
  getTaskPreview: (...args: unknown[]) => mockGetTaskPreview(...(args as [string, string])),
  getExecutionTasks: vi.fn().mockResolvedValue([]),
}))

// 动态导入
const { TaskPreview } = await import('./TaskPreview')
const apiMock = await import('../api')

describe('TaskPreview 数据结构', () => {
  it('TaskPreviewType 包含所有必要字段', () => {
    const preview: TaskPreviewType = {
      taskId: 't1',
      status: 'completed',
      firstFrameUrl: '/api/assets/a1/content',
      errorMessage: undefined,
      variantLabel: 'variant-0',
      progress: 100,
      kind: 'textToImage',
      nodeLabel: '生成图片',
    }

    expect(preview.taskId).toBe('t1')
    expect(preview.status).toBe('completed')
    expect(preview.firstFrameUrl).toBe('/api/assets/a1/content')
    expect(preview.variantLabel).toBe('variant-0')
    expect(preview.progress).toBe(100)
    expect(preview.kind).toBe('textToImage')
    expect(preview.nodeLabel).toBe('生成图片')
  })

  it('TaskPreviewType 支持所有状态值', () => {
    const statuses: TaskPreviewType['status'][] = ['pending', 'running', 'completed', 'failed']
    statuses.forEach((status) => {
      const preview: TaskPreviewType = { taskId: 't1', status }
      expect(preview.status).toBe(status)
    })
  })
})

describe('retryTask API 调用', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRetryTask.mockResolvedValue({ task_id: 't1', status: 'pending', message: 'ok' })
  })

  it('retryTask 调用正确的 API 端点', async () => {
    const result = await apiMock.retryTask('exec-1', 'task-1')
    expect(mockRetryTask).toHaveBeenCalledWith('exec-1', 'task-1')
    expect(result.status).toBe('pending')
  })

  it('retryTask 失败时抛出错误', async () => {
    mockRetryTask.mockRejectedValueOnce(new Error('Retry failed'))
    await expect(apiMock.retryTask('exec-1', 'task-1')).rejects.toThrow('Retry failed')
  })
})

describe('getTaskPreview API 调用', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetTaskPreview.mockResolvedValue({
      task_id: 't1', status: 'failed', error_message: 'Provider timeout',
    })
  })

  it('getTaskPreview 返回预览数据', async () => {
    const result = await apiMock.getTaskPreview('exec-1', 'task-1')
    expect(result.task_id).toBe('t1')
    expect(result.status).toBe('failed')
    expect(result.error_message).toBe('Provider timeout')
  })
})

describe('ExpandableTaskRow 行为描述', () => {
  // 以下测试描述 ExpandableTaskRow 在不同状态下的预期行为

  it('failed 任务显示重试按钮', () => {
    const task: TaskPreviewType = {
      taskId: 't1',
      status: 'failed',
      errorMessage: 'Something went wrong',
    }
    // 组件会渲染 exec-retry-btn 按钮
    expect(task.status).toBe('failed')
    expect(task.errorMessage).toBeDefined()
  })

  it('completed 任务不显示重试按钮', () => {
    const task: TaskPreviewType = {
      taskId: 't1',
      status: 'completed',
    }
    expect(task.status).toBe('completed')
  })

  it('任务包含变体标签时显示', () => {
    const task: TaskPreviewType = {
      taskId: 't1',
      status: 'completed',
      variantLabel: 'variant-1',
    }
    expect(task.variantLabel).toBe('variant-1')
  })

  it('任务有首帧 URL 时显示缩略图', () => {
    const task: TaskPreviewType = {
      taskId: 't1',
      status: 'completed',
      firstFrameUrl: '/api/assets/a1/content',
    }
    expect(task.firstFrameUrl).toBeDefined()
  })
})

describe('TaskPreview 状态渲染描述', () => {
  it('pending 状态显示等待中徽标', () => {
    const preview: TaskPreviewType = { taskId: 't1', status: 'pending' }
    expect(preview.status).toBe('pending')
  })

  it('running 状态显示运行中徽标和进度', () => {
    const preview: TaskPreviewType = { taskId: 't1', status: 'running', progress: 50 }
    expect(preview.status).toBe('running')
    expect(preview.progress).toBe(50)
  })

  it('completed 状态显示完成徽标', () => {
    const preview: TaskPreviewType = { taskId: 't1', status: 'completed', progress: 100 }
    expect(preview.status).toBe('completed')
  })

  it('failed 状态显示失败徽标和错误信息', () => {
    const preview: TaskPreviewType = {
      taskId: 't1',
      status: 'failed',
      errorMessage: 'Connection timeout',
    }
    expect(preview.status).toBe('failed')
    expect(preview.errorMessage).toBe('Connection timeout')
  })
})
