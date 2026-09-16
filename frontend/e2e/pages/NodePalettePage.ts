import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the NodePalette (sidebar with node types).
 * Provides methods to interact with node catalog items and add nodes to the canvas.
 */
export class NodePalettePage {
  readonly page: Page
  readonly panel: Locator
  readonly heading: Locator
  readonly hint: Locator
  readonly nodeList: Locator
  readonly footer: Locator

  constructor(page: Page) {
    this.page = page
    this.panel = page.locator('aside.palette')
    this.heading = this.panel.locator('.panel-heading')
    this.hint = this.panel.locator('.panel-hint')
    this.nodeList = this.panel.locator('.node-list')
    this.footer = this.panel.locator('.palette-footer')
  }

  /** Wait until the palette is fully rendered. */
  async waitForReady() {
    await this.panel.waitFor({ state: 'visible' })
  }

  /** Get all node kind buttons in the palette. */
  getNodes(): Locator {
    return this.nodeList.locator('button')
  }

  /** Get a specific node by its label text. */
  getNodeByLabel(label: string): Locator {
    return this.nodeList.locator('button', { hasText: label })
  }

  /** Click a node kind to add it to the canvas. */
  async addNodeByLabel(label: string) {
    await this.getNodeByLabel(label).click()
  }

  /** Get the count of available node kinds. */
  async getNodeCount(): Promise<number> {
    return this.getNodes().count()
  }

  /** Check if the palette footer shows connected status. */
  async isConnected(): Promise<boolean> {
    const text = await this.footer.textContent()
    return text?.includes('已连接') ?? false
  }
}
