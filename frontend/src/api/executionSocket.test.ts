import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

// 模拟 window 对象（Node.js 环境中不存在）
if (typeof globalThis.window === 'undefined') {
  // 测试环境补丁 — 部分 Location 属性足够测试使用
  ;(globalThis as any).window = {
    location: {
      protocol: 'http:',
      host: 'localhost:5173',
    },
  }
}

/**
 * Mock WebSocket — 模拟浏览器 WebSocket 行为，用于单元测试。
 */
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  static instances: MockWebSocket[] = []
  static lastInstance(): MockWebSocket {
    const last = MockWebSocket.instances[MockWebSocket.instances.length - 1]
    if (!last) throw new Error('No MockWebSocket instance created')
    return last
  }
  static reset() {
    MockWebSocket.instances = []
  }

  readyState = MockWebSocket.CONNECTING
  url: string
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onerror: ((ev: unknown) => void) | null = null
  send = vi.fn()
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED
  })

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }
}

// 在所有 import 之前注入全局 mock
vi.stubGlobal('WebSocket', MockWebSocket)

// 使用动态导入确保 mock 已就位
const { ExecutionSocket } = await import('./executionSocket')

describe('ExecutionSocket', () => {
  beforeEach(() => {
    MockWebSocket.reset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('connect creates a WebSocket to the correct URL', () => {
    const socket = new ExecutionSocket('exec-abc')
    socket.connect()
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.lastInstance().url).toContain('exec-abc')
  })

  it('reports connecting status immediately on connect', () => {
    const socket = new ExecutionSocket('exec-1')
    const statusHandler = vi.fn()
    socket.onStatusChange(statusHandler)
    socket.connect()

    expect(statusHandler).toHaveBeenCalledWith('connecting')
  })

  it('reports connected status when WebSocket opens', () => {
    const socket = new ExecutionSocket('exec-1')
    const statusHandler = vi.fn()
    socket.onStatusChange(statusHandler)
    socket.connect()

    MockWebSocket.lastInstance().simulateOpen()
    expect(statusHandler).toHaveBeenCalledWith('connected')
  })

  it('delivers parsed events to the event handler', () => {
    const socket = new ExecutionSocket('exec-1')
    const eventHandler = vi.fn()
    socket.onEvent(eventHandler)
    socket.connect()
    MockWebSocket.lastInstance().simulateOpen()

    const event = {
      event_id: 'evt-1',
      execution_id: 'exec-1',
      node_id: 'node-a',
      type: 'node.started',
      status: 'running',
      progress: 0,
      message: 'task started',
      timestamp: '2025-01-01T00:00:00Z',
    }
    MockWebSocket.lastInstance().simulateMessage(event)

    expect(eventHandler).toHaveBeenCalledWith(event)
    expect(eventHandler).toHaveBeenCalledTimes(1)
  })

  it('tracks lastEventId from received messages', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.onEvent(vi.fn())
    socket.connect()
    const ws1 = MockWebSocket.lastInstance()
    ws1.simulateOpen()

    ws1.simulateMessage({
      event_id: 'evt-42',
      execution_id: 'exec-1',
      node_id: 'n1',
      type: 'node.completed',
      status: 'completed',
      progress: 100,
      message: 'done',
      timestamp: '2025-01-01T00:00:01Z',
    })

    // 断开后重连
    ws1.simulateClose()
    vi.advanceTimersByTime(1000)
    const ws2 = MockWebSocket.lastInstance()
    ws2.simulateOpen()

    // 重连后应发送 replay 消息补拉缺失事件
    expect(ws2.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'replay', last_event_id: 'evt-42' }),
    )
  })

  it('reports disconnected on close and triggers reconnection', () => {
    const socket = new ExecutionSocket('exec-1')
    const statusHandler = vi.fn()
    socket.onStatusChange(statusHandler)
    socket.connect()
    MockWebSocket.lastInstance().simulateOpen()

    MockWebSocket.lastInstance().simulateClose()
    expect(statusHandler).toHaveBeenCalledWith('disconnected')

    // 初始连接 + 1 次重连
    expect(MockWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it('uses exponential backoff for reconnection delays', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()

    // 第 1 次断开 → 1s 后重连
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(999)
    expect(MockWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(MockWebSocket.instances).toHaveLength(2)

    // 第 2 次断开 → 2s 后重连
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(1999)
    expect(MockWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(MockWebSocket.instances).toHaveLength(3)

    // 第 3 次断开 → 4s 后重连
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(3999)
    expect(MockWebSocket.instances).toHaveLength(3)
    vi.advanceTimersByTime(1)
    expect(MockWebSocket.instances).toHaveLength(4)
  })

  it('stops reconnecting after maxReconnectAttempts (10)', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()

    // 连续断开 10 次，每次等足够长的时间让重连触发
    for (let i = 0; i < 10; i++) {
      MockWebSocket.lastInstance().simulateClose()
      vi.advanceTimersByTime(30000)
    }

    // 10 次重连 + 原始连接 = 11 个实例
    expect(MockWebSocket.instances).toHaveLength(11)

    // 再断开一次，不应再重连
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(30000)
    expect(MockWebSocket.instances).toHaveLength(11)
  })

  it('disconnect stops all reconnection attempts', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()
    MockWebSocket.lastInstance().simulateOpen()

    // 断开后立即调用 disconnect
    MockWebSocket.lastInstance().simulateClose()
    socket.disconnect()

    // 等待足够时间，不应重连
    vi.advanceTimersByTime(10000)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('reset reconnect counter on successful open', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()

    // 第 1 次断开 → 重连
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)

    // 重连成功
    MockWebSocket.lastInstance().simulateOpen()

    // 再断开 → 应该从 0 开始计数，1s 后重连（不是 2s）
    MockWebSocket.lastInstance().simulateClose()
    vi.advanceTimersByTime(999)
    expect(MockWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('does not send replay on first connect without lastEventId', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()
    const ws = MockWebSocket.lastInstance()
    ws.simulateOpen()

    // 首次连接不应发送 replay 消息
    expect(ws.send).not.toHaveBeenCalled()
  })

  it('ignores unparseable messages gracefully', () => {
    const socket = new ExecutionSocket('exec-1')
    const eventHandler = vi.fn()
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    socket.onEvent(eventHandler)
    socket.connect()
    MockWebSocket.lastInstance().simulateOpen()

    // 发送无效 JSON
    MockWebSocket.lastInstance().onmessage?.({ data: 'not-json' })

    expect(eventHandler).not.toHaveBeenCalled()
    expect(consoleSpy).toHaveBeenCalled()
    consoleSpy.mockRestore()
  })

  it('disconnect closes the underlying WebSocket', () => {
    const socket = new ExecutionSocket('exec-1')
    socket.connect()
    const ws = MockWebSocket.lastInstance()

    socket.disconnect()

    expect(ws.close).toHaveBeenCalled()
  })
})
