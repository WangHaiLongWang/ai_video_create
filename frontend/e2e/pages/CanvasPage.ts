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
}
