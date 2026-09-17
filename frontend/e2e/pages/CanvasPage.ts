import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the Canvas (React Flow workspace).
 * Provides methods to interact with workflow nodes, edges, and canvas controls.
 */
export class CanvasPage {
  readonly page: Page
  readonly shell: Locator
  readonly reactFlowViewport: Locator
  readonly controls: Locator
  readonly miniMap: Locator
  readonly agentComposer: Locator

  constructor(page: Page) {
    this.page = page
    this.shell = page.locator('main.canvas-shell')
    this.reactFlowViewport = this.shell.locator('.react-flow__viewport')
    this.controls = this.shell.locator('.react-flow__controls')
    this.miniMap = this.shell.locator('.react-flow__minimap')
    this.agentComposer = this.shell.locator('.agent-composer')
  }

  /** Wait until the canvas is fully rendered. */
  async waitForReady() {
    await this.shell.waitFor({ state: 'visible' })
    await this.reactFlowViewport.waitFor({ state: 'visible' })
  }

  /** Get all rendered workflow nodes. */
  getNodes(): Locator {
    return this.shell.locator('.react-flow__node')
  }

  /** Get a specific node by its label. */
  getNodeByLabel(label: string): Locator {
    return this.shell.locator('.react-flow__node', { hasText: label })
  }

  /** Get the count of visible nodes. */
  async getNodeCount(): Promise<number> {
    return this.getNodes().count()
  }

  /** Click on a node by its label to select it. */
  async selectNode(label: string) {
    await this.getNodeByLabel(label).click()
  }

  /** Click on the canvas pane to deselect any selected node. */
  async deselectNodes() {
    // Click on the React Flow background area (not on a node)
    await this.reactFlowViewport.click({ position: { x: 10, y: 10 } })
  }

  /** Get a node's status CSS class. */
  async getNodeStatus(label: string): Promise<string | null> {
    const node = this.getNodeByLabel(label)
    const className = await node.locator('.studio-node').getAttribute('class')
    if (!className) return null
    const match = className.match(/status-(\w+)/)
    return match ? match[1] : null
  }

  /** Get all rendered edges. */
  getEdges(): Locator {
    return this.shell.locator('.react-flow__edge')
  }

  /** Get the count of visible edges. */
  async getEdgeCount(): Promise<number> {
    return this.getEdges().count()
  }

  /** Drag a node by its label to a new position. */
  async dragNode(label: string, deltaX: number, deltaY: number) {
    const node = this.getNodeByLabel(label)
    const box = await node.boundingBox()
    if (!box) throw new Error(`Node "${label}" not found on canvas`)

    const startX = box.x + box.width / 2
    const startY = box.y + box.height / 2

    await this.page.mouse.move(startX, startY)
    await this.page.mouse.down()
    // Move in small steps so React Flow picks up the drag
    const steps = 5
    for (let i = 1; i <= steps; i++) {
      await this.page.mouse.move(
        startX + (deltaX * i) / steps,
        startY + (deltaY * i) / steps,
      )
    }
    await this.page.mouse.up()
  }

  /** Zoom controls */
  async zoomIn() {
    await this.controls.locator('button[title="Zoom in"]').click()
  }

  async zoomOut() {
    await this.controls.locator('button[title="Zoom out"]').click()
  }

  async fitView() {
    await this.controls.locator('button[title="Fit view"]').click()
  }

  // --- Connection methods ---

  /** Get a node's handle by port ID. */
  getHandle(nodeLabel: string, handleId: string, type: 'source' | 'target'): Locator {
    const node = this.getNodeByLabel(nodeLabel)
    const handleClass = type === 'source' ? '.react-flow__handle.source' : '.react-flow__handle.target'
    // React Flow renders Handle id as data-handleid attribute
    return node.locator(`${handleClass}[data-handleid="${handleId}"]`)
  }

  /** Connect two nodes by dragging from source handle to target handle. */
  async connectNodes(
    sourceLabel: string, sourceHandleId: string,
    targetLabel: string, targetHandleId: string,
  ) {
    const source = this.getHandle(sourceLabel, sourceHandleId, 'source')
    const target = this.getHandle(targetLabel, targetHandleId, 'target')

    const sourceBox = await source.boundingBox()
    const targetBox = await target.boundingBox()
    if (!sourceBox || !targetBox) throw new Error('Handle not found')

    const sx = sourceBox.x + sourceBox.width / 2
    const sy = sourceBox.y + sourceBox.height / 2
    const tx = targetBox.x + targetBox.width / 2
    const ty = targetBox.y + targetBox.height / 2

    await this.page.mouse.move(sx, sy)
    await this.page.mouse.down()
    // Move in steps so React Flow picks up the drag
    const steps = 10
    for (let i = 1; i <= steps; i++) {
      await this.page.mouse.move(
        sx + ((tx - sx) * i) / steps,
        sy + ((ty - sy) * i) / steps,
      )
    }
    await this.page.mouse.up()
  }

  /** Get the connection error toast message, if visible. */
  async getConnectionError(): Promise<string | null> {
    const toast = this.page.locator('.toast-message, [role="alert"]')
    if (await toast.isVisible().catch(() => false)) {
      return toast.textContent()
    }
    return null
  }

  /** Check if a specific edge exists between two nodes. */
  async hasEdge(sourceId: string, targetId: string): Promise<boolean> {
    // React Flow 12 renders edge <g> elements with role="button" and aria-label
    // in the format "Edge from {source} to {target}"
    const edge = this.shell.locator(
      `.react-flow__edge[aria-label="Edge from ${sourceId} to ${targetId}"]`,
    )
    return edge.count().then(c => c > 0)
  }
}
