import type { ExecutionEvent } from '../api'

type EventHandler = (event: ExecutionEvent) => void
type StatusHandler = (status: 'connecting' | 'connected' | 'disconnected') => void

export class ExecutionSocket {
  private ws: WebSocket | null = null
  private executionId: string
  private url: string
  private eventHandler: EventHandler | null = null
  private statusHandler: StatusHandler | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private lastEventId: string | null = null
  private explicitDisconnect = false

  constructor(executionId: string) {
    this.executionId = executionId
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.host}/api/executions/${executionId}/ws`
  }

  connect() {
    this.explicitDisconnect = false
    this.statusHandler?.('connecting')
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.statusHandler?.('connected')
      if (this.lastEventId) {
        this.ws?.send(JSON.stringify({ type: 'replay', last_event_id: this.lastEventId }))
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ExecutionEvent
        this.lastEventId = data.event_id || null
        this.eventHandler?.(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    this.ws.onclose = () => {
      this.statusHandler?.('disconnected')
      if (!this.explicitDisconnect) {
        this.tryReconnect()
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.ws?.close()
    }
  }

  private tryReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    this.reconnectAttempts++
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }

  disconnect() {
    this.explicitDisconnect = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  onEvent(handler: EventHandler) { this.eventHandler = handler }
  onStatusChange(handler: StatusHandler) { this.statusHandler = handler }
}
