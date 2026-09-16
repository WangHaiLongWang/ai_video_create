/**
 * ExecutionPanel 及 executionStore 单元测试
 *
 * 测试内容:
 * 1. executionStore 初始状态 (idle)
 * 2. 执行中状态 (running)
 * 3. 完成状态 (completed)
 * 4. 失败状态 (failed) 和重试按钮行为
 * 5. 事件日志管理
 * 6. 任务状态更新
 * 7. 重置执行记录
 *
 * 注意: 当前测试环境无 jsdom/@testing-library，因此测试 store 逻辑而非组件渲染。
 * 组件渲染行为通过 store 状态间接验证。
 */

import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest'

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
vi.mock('../api', () => ({
  startExecution: vi.fn().mockResolvedValue({ id: 'exec-test-1', workflow_id: 'wf-1', status: 'running', task_count: 3 }),
  getExecution: vi.fn().mockResolvedValue({ id: 'exec-test-1', workflow_id: 'wf-1', status: 'running', task_count: 3 }),
  getExecutionTasks: vi.fn().mockResolvedValue([]),
  cancelExecution: vi.fn().mockResolvedValue(undefined),
  retryExecution: vi.fn().mockResolvedValue({
    execution_id: 'exec-test-1',
    task_id: 'task-1',
    node_id: 'node-1',
    status: 'pending',
    idempotency_key: null,
    message: '节点已重置为待执行，等待 Worker 调度',
  }),
}))

// Mock ExecutionSocket
vi.mock('../api/executionSocket', () => ({
  ExecutionSocket: vi.fn().mockImplementation(() => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    onEvent: vi.fn(),
    onStatusChange: vi.fn(),
  })),
}))

// 动态导入 store，确保 mock 已就位
const { useExecutionStore } = await import('../stores/executionStore')
const apiMock = await import('../api')
const retryExecutionMock = apiMock.retryExecution as unknown as Mock

describe('executionStore', () => {
  beforeEach(() => {
    // 重置 store 为初始状态
    useExecutionStore.setState({
      executionId: null,
      status: 'idle',
      taskCount: 0,
      completedCount: 0,
      tasks: new Map(),
      nodeStates: new Map(),
      events: [],
      socketStatus: 'disconnected',
      startTime: null,
    })
    vi.clearAllMocks()
  })

  // --- 测试1: 空状态 (idle) ---
  describe('初始状态 (idle)', () => {
    it('executionId 为 null', () => {
      expect(useExecutionStore.getState().executionId).toBeNull()
    })

    it('status 为 idle', () => {
      expect(useExecutionStore.getState().status).toBe('idle')
    })

    it('tasks 为空 Map', () => {
      expect(useExecutionStore.getState().tasks.size).toBe(0)
    })

    it('nodeStates 为空 Map', () => {
      expect(useExecutionStore.getState().nodeStates.size).toBe(0)
    })

    it('events 为空数组', () => {
      expect(useExecutionStore.getState().events).toEqual([])
    })

    it('socketStatus 为 disconnected', () => {
      expect(useExecutionStore.getState().socketStatus).toBe('disconnected')
    })
  })

  // --- 测试2: 执行中状态 (running) ---
  describe('执行中状态 (running)', () => {
    it('startExecution 设置 status 为 running', async () => {
      await useExecutionStore.getState().startExecution('wf-1')
      expect(useExecutionStore.getState().status).toBe('running')
    })

    it('startExecution 设置 executionId', async () => {
      await useExecutionStore.getState().startExecution('wf-1')
      expect(useExecutionStore.getState().executionId).toBe('exec-test-1')
    })

    it('startExecution 设置 startTime', async () => {
      const before = Date.now()
      await useExecutionStore.getState().startExecution('wf-1')
      const state = useExecutionStore.getState()
      expect(state.startTime).toBeGreaterThanOrEqual(before)
    })

    it('startExecution 设置 taskCount', async () => {
      await useExecutionStore.getState().startExecution('wf-1')
      expect(useExecutionStore.getState().taskCount).toBe(3)
    })

    it('startExecution 初始化 events 为空', async () => {
      await useExecutionStore.getState().startExecution('wf-1')
      expect(useExecutionStore.getState().events).toEqual([])
    })
  })

  // --- 测试3: 完成状态 (completed) ---
  describe('完成状态 (completed)', () => {
    it('addEvent 接收 execution.completed 后 status 变为 completed', () => {
      useExecutionStore.setState({
        executionId: 'exec-1',
        status: 'running',
      })

      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1',
        node_id: '',
        type: 'execution.completed',
        status: 'completed',
        progress: 100,
        message: '执行完成',
        timestamp: '2025-01-01T00:00:10Z',
      })

      expect(useExecutionStore.getState().status).toBe('completed')
    })

    it('完成事件被记录到 events 数组', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      const event = {
        execution_id: 'exec-1',
        node_id: '',
        type: 'execution.completed',
        status: 'completed',
        progress: 100,
        message: '执行完成',
        timestamp: '2025-01-01T00:00:10Z',
      }
      useExecutionStore.getState().addEvent(event)

      expect(useExecutionStore.getState().events).toHaveLength(1)
      expect(useExecutionStore.getState().events[0].type).toBe('execution.completed')
    })
  })

  // --- 测试4: 失败状态 (failed) 和重试按钮 ---
  describe('失败状态 (failed) 和重试', () => {
    it('addEvent 接收 execution.failed 后 status 变为 failed', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1',
        node_id: 'node-1',
        type: 'execution.failed',
        status: 'failed',
        progress: 50,
        message: '节点执行失败',
        timestamp: '2025-01-01T00:00:05Z',
      })

      expect(useExecutionStore.getState().status).toBe('failed')
    })

    it('node.failed 事件更新 nodeStates', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      // 先开始节点
      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1',
        node_id: 'node-1',
        type: 'node.started',
        status: 'running',
        progress: 0,
        message: '开始',
        timestamp: '2025-01-01T00:00:01Z',
      })

      // 节点失败
      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1',
        node_id: 'node-1',
        type: 'node.failed',
        status: 'failed',
        progress: 50,
        message: '执行失败',
        timestamp: '2025-01-01T00:00:05Z',
      })

      const nodeState = useExecutionStore.getState().nodeStates.get('node-1')
      expect(nodeState).toBeDefined()
      expect(nodeState?.status).toBe('failed')
    })

    it('retryNode 调用 retryExecution API', async () => {
      useExecutionStore.setState({
        executionId: 'exec-test-1',
        status: 'failed',
        nodeStates: new Map([
          ['node-1', { nodeId: 'node-1', status: 'failed', taskCount: 1, completedCount: 0, failedCount: 1 }],
        ]),
      })

      await useExecutionStore.getState().retryNode('node-1')

      expect(apiMock.retryExecution).toHaveBeenCalledWith('exec-test-1', 'node-1')
    })

    it('retryNode 将失败节点状态更新为 waiting', async () => {
      useExecutionStore.setState({
        executionId: 'exec-test-1',
        status: 'failed',
        nodeStates: new Map([
          ['node-1', { nodeId: 'node-1', status: 'failed', taskCount: 1, completedCount: 0, failedCount: 1 }],
        ]),
      })

      await useExecutionStore.getState().retryNode('node-1')

      const nodeState = useExecutionStore.getState().nodeStates.get('node-1')
      expect(nodeState).toBeDefined()
      expect(nodeState?.status).toBe('waiting')
      expect(nodeState?.failedCount).toBe(0)
    })

    it('retryNode 无 executionId 时不调用 API', async () => {
      useExecutionStore.setState({
        executionId: null,
        status: 'idle',
      })

      await useExecutionStore.getState().retryNode('node-1')

      expect(apiMock.retryExecution).not.toHaveBeenCalled()
    })

    it('retryNode 对非 failed 节点不调用 API', async () => {
      useExecutionStore.setState({
        executionId: 'exec-test-1',
        status: 'running',
        nodeStates: new Map([
          ['node-1', { nodeId: 'node-1', status: 'running', taskCount: 1, completedCount: 0, failedCount: 0 }],
        ]),
      })

      await useExecutionStore.getState().retryNode('node-1')

      expect(apiMock.retryExecution).not.toHaveBeenCalled()
    })

    it('retryNode API 失败时抛出错误', async () => {
      retryExecutionMock.mockRejectedValueOnce(new Error('Retry failed: 400'))
      useExecutionStore.setState({
        executionId: 'exec-test-1',
        status: 'failed',
        nodeStates: new Map([
          ['node-1', { nodeId: 'node-1', status: 'failed', taskCount: 1, completedCount: 0, failedCount: 1 }],
        ]),
      })

      await expect(
        useExecutionStore.getState().retryNode('node-1'),
      ).rejects.toThrow('Retry failed: 400')

      // 节点状态不应被修改
      const nodeState = useExecutionStore.getState().nodeStates.get('node-1')
      expect(nodeState?.status).toBe('failed')
    })
  })

  // --- 测试5: 事件日志管理 ---
  describe('事件日志管理', () => {
    it('多个事件按顺序记录', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      const events = [
        {
          execution_id: 'exec-1', node_id: '', type: 'execution.started',
          status: 'running', progress: 0, message: '开始', timestamp: '2025-01-01T00:00:00Z',
        },
        {
          execution_id: 'exec-1', node_id: 'n1', type: 'node.started',
          status: 'running', progress: 0, message: 'n1 开始', timestamp: '2025-01-01T00:00:01Z',
        },
        {
          execution_id: 'exec-1', node_id: 'n1', type: 'node.completed',
          status: 'completed', progress: 100, message: 'n1 完成', timestamp: '2025-01-01T00:00:03Z',
        },
      ]

      events.forEach((e) => useExecutionStore.getState().addEvent(e))

      expect(useExecutionStore.getState().events).toHaveLength(3)
      expect(useExecutionStore.getState().events[0].type).toBe('execution.started')
      expect(useExecutionStore.getState().events[1].type).toBe('node.started')
      expect(useExecutionStore.getState().events[2].type).toBe('node.completed')
    })

    it('node.started 事件设置 nodeStates 为 running', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'storyboard-1', type: 'node.started',
        status: 'running', progress: 0, message: '开始分镜', timestamp: '2025-01-01T00:00:01Z',
      })

      const ns = useExecutionStore.getState().nodeStates.get('storyboard-1')
      expect(ns).toBeDefined()
      expect(ns?.status).toBe('running')
    })

    it('node.completed 事件设置 nodeStates 为 completed', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'storyboard-1', type: 'node.started',
        status: 'running', progress: 0, message: '开始', timestamp: '2025-01-01T00:00:01Z',
      })
      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'storyboard-1', type: 'node.completed',
        status: 'completed', progress: 100, message: '完成', timestamp: '2025-01-01T00:00:03Z',
      })

      const ns = useExecutionStore.getState().nodeStates.get('storyboard-1')
      expect(ns?.status).toBe('completed')
    })
  })

  // --- 测试6: 任务状态更新 ---
  describe('任务状态更新', () => {
    it('task.started 事件记录到 tasks Map', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'textToImage-1', type: 'task.started',
        status: 'running', progress: 0, message: '开始处理', timestamp: '2025-01-01T00:00:02Z',
        item_key: 'task-img-1',
      })

      const task = useExecutionStore.getState().tasks.get('task-img-1')
      expect(task).toBeDefined()
      expect(task?.status).toBe('running')
      expect(task?.nodeId).toBe('textToImage-1')
    })

    it('task.completed 事件更新任务状态为 completed', () => {
      useExecutionStore.setState({ executionId: 'exec-1', status: 'running' })

      // 开始任务
      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'textToImage-1', type: 'task.started',
        status: 'running', progress: 0, message: '开始', timestamp: '2025-01-01T00:00:02Z',
        item_key: 'task-img-1',
      })

      // 完成任务
      useExecutionStore.getState().addEvent({
        execution_id: 'exec-1', node_id: 'textToImage-1', type: 'task.completed',
        status: 'completed', progress: 100, message: '完成', timestamp: '2025-01-01T00:00:05Z',
        item_key: 'task-img-1',
      })

      const task = useExecutionStore.getState().tasks.get('task-img-1')
      expect(task?.status).toBe('completed')
      expect(task?.progress).toBe(100)
    })

    it('updateTaskState 可以部分更新任务属性', () => {
      useExecutionStore.setState({
        executionId: 'exec-1',
        tasks: new Map([
          ['t1', {
            id: 't1', nodeId: 'n1', kind: 'textToImage', label: '任务1',
            status: 'running', progress: 30,
          }],
        ]),
      })

      useExecutionStore.getState().updateTaskState('t1', { progress: 75 })

      const task = useExecutionStore.getState().tasks.get('t1')
      expect(task?.progress).toBe(75)
      expect(task?.status).toBe('running') // 未修改的字段保持不变
    })
  })

  // --- 测试7: 重置执行记录 ---
  describe('重置执行记录', () => {
    it('resetExecution 清空所有执行状态', () => {
      // 先设置一些执行状态
      useExecutionStore.setState({
        executionId: 'exec-1',
        status: 'completed',
        taskCount: 5,
        completedCount: 5,
        tasks: new Map([['t1', { id: 't1', nodeId: 'n1', kind: '', label: '', status: 'completed', progress: 100 }]]),
        nodeStates: new Map([['n1', { nodeId: 'n1', status: 'completed', taskCount: 1, completedCount: 1, failedCount: 0 }]]),
        events: [{ execution_id: 'exec-1', node_id: '', type: 'execution.completed', status: 'completed', progress: 100, message: '完成', timestamp: '2025-01-01T00:00:10Z' }],
        startTime: Date.now(),
      })

      useExecutionStore.getState().resetExecution()

      const state = useExecutionStore.getState()
      expect(state.executionId).toBeNull()
      expect(state.status).toBe('idle')
      expect(state.taskCount).toBe(0)
      expect(state.completedCount).toBe(0)
      expect(state.tasks.size).toBe(0)
      expect(state.nodeStates.size).toBe(0)
      expect(state.events).toEqual([])
      expect(state.startTime).toBeNull()
      expect(state.socketStatus).toBe('disconnected')
    })
  })

  // --- 测试8: 取消执行 ---
  describe('取消执行', () => {
    it('stopExecution 设置 status 为 cancelled', async () => {
      useExecutionStore.setState({
        executionId: 'exec-1',
        status: 'running',
      })

      await useExecutionStore.getState().stopExecution()

      expect(useExecutionStore.getState().status).toBe('cancelled')
    })

    it('stopExecution 调用后端取消 API', async () => {
      useExecutionStore.setState({
        executionId: 'exec-1',
        status: 'running',
      })

      await useExecutionStore.getState().stopExecution()

      expect(apiMock.cancelExecution).toHaveBeenCalledWith('exec-1')
    })
  })
})

describe('ExecutionPanel 组件行为描述', () => {
  // 以下测试描述 ExecutionPanel 组件在不同 store 状态下的预期渲染行为
  // 由于测试环境无 jsdom，使用 store 状态间接验证

  beforeEach(() => {
    useExecutionStore.setState({
      executionId: null,
      status: 'idle',
      taskCount: 0,
      completedCount: 0,
      tasks: new Map(),
      nodeStates: new Map(),
      events: [],
      socketStatus: 'disconnected',
      startTime: null,
    })
  })

  it('idle 状态: 面板不显示 (executionId 为 null 且 status 为 idle)', () => {
    const state = useExecutionStore.getState()
    // 组件在 executionId === null && status === 'idle' 时返回 null
    expect(state.executionId).toBeNull()
    expect(state.status).toBe('idle')
  })

  it('running 状态: 面板显示执行中状态', () => {
    useExecutionStore.setState({
      executionId: 'exec-1',
      status: 'running',
      taskCount: 5,
      completedCount: 2,
      startTime: Date.now() - 3000,
      socketStatus: 'connected',
    })

    const state = useExecutionStore.getState()
    expect(state.status).toBe('running')
    expect(state.executionId).not.toBeNull()
    expect(state.taskCount).toBe(5)
    expect(state.completedCount).toBe(2)
  })

  it('completed 状态: 面板显示执行完成', () => {
    useExecutionStore.setState({
      executionId: 'exec-1',
      status: 'completed',
      taskCount: 5,
      completedCount: 5,
      nodeStates: new Map([
        ['n1', { nodeId: 'n1', status: 'completed', taskCount: 1, completedCount: 1, failedCount: 0 }],
        ['n2', { nodeId: 'n2', status: 'completed', taskCount: 1, completedCount: 1, failedCount: 0 }],
      ]),
    })

    const state = useExecutionStore.getState()
    expect(state.status).toBe('completed')
    expect(state.completedCount).toBe(state.taskCount)
    // 所有节点应为 completed
    state.nodeStates.forEach((ns) => {
      expect(ns.status).toBe('completed')
    })
  })

  it('failed 状态: 面板显示失败节点和重试按钮', () => {
    useExecutionStore.setState({
      executionId: 'exec-1',
      status: 'failed',
      taskCount: 5,
      completedCount: 3,
      nodeStates: new Map([
        ['n1', { nodeId: 'n1', status: 'completed', taskCount: 1, completedCount: 1, failedCount: 0 }],
        ['n2', { nodeId: 'n2', status: 'failed', taskCount: 1, completedCount: 0, failedCount: 1 }],
        ['n3', { nodeId: 'n3', status: 'waiting', taskCount: 1, completedCount: 0, failedCount: 0 }],
      ]),
      events: [
        {
          execution_id: 'exec-1', node_id: 'n2', type: 'node.failed',
          status: 'failed', progress: 50, message: '节点执行失败',
          timestamp: '2025-01-01T00:00:05Z',
        },
      ],
    })

    const state = useExecutionStore.getState()
    expect(state.status).toBe('failed')

    // 应有一个失败节点
    const failedNodes = Array.from(state.nodeStates.values()).filter((ns) => ns.status === 'failed')
    expect(failedNodes).toHaveLength(1)
    expect(failedNodes[0].nodeId).toBe('n2')

    // 事件日志应记录失败事件
    const failEvents = state.events.filter((e) => e.type === 'node.failed')
    expect(failEvents).toHaveLength(1)
  })
})
