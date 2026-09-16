import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the TopBar component.
 * Provides methods to interact with the header bar, run/stop controls,
 * settings, and template buttons.
 */
export class TopBarPage {
  readonly page: Page
  readonly header: Locator
  readonly brandTitle: Locator
  readonly workflowNameButton: Locator
  readonly runButton: Locator
  readonly stopButton: Locator
  readonly settingsButton: Locator
  readonly templateButton: Locator
  readonly autoSaveStatus: Locator
  readonly executionStatus: Locator

  constructor(page: Page) {
    this.page = page
    this.header = page.locator('header.topbar')
    this.brandTitle = this.header.locator('strong', { hasText: 'ai_video_create' })
    this.workflowNameButton = this.header.locator('.title-group button')
    this.runButton = this.header.locator('.run-button')
    this.stopButton = this.header.locator('.stop-button')
    this.settingsButton = this.header.locator('button[aria-label="设置"]')
    this.templateButton = this.header.locator('button[aria-label="模板"]')
    this.autoSaveStatus = this.header.locator('.secondary-button')
    this.executionStatus = this.header.locator('.execution-status')
  }

  /** Wait until the top bar is fully rendered. */
  async waitForReady() {
    await this.header.waitFor({ state: 'visible' })
    await this.brandTitle.waitFor({ state: 'visible' })
  }

  /** Click the "Run Workflow" button. */
  async clickRun() {
    await this.runButton.click()
  }

  /** Click the "Stop" button (visible only during execution). */
  async clickStop() {
    await this.stopButton.click()
  }

  /** Open the settings panel. */
  async openSettings() {
    await this.settingsButton.click()
  }

  /** Open the template selector. */
  async openTemplates() {
    await this.templateButton.click()
  }

  /** Get the current workflow name displayed in the title bar. */
  async getWorkflowName(): Promise<string> {
    return (await this.workflowNameButton.textContent()) ?? ''
  }

  /** Check if execution status bar is visible. */
  async isExecutionStatusVisible(): Promise<boolean> {
    return this.executionStatus.isVisible()
  }
}
