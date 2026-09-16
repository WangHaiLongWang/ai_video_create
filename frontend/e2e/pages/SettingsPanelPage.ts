import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the SettingsPanel (modal overlay for app configuration).
 * Covers provider selection, provider-specific config sections, and save/test actions.
 */
export class SettingsPanelPage {
  readonly page: Page
  readonly overlay: Locator
  readonly panel: Locator
  readonly title: Locator
  readonly closeButton: Locator
  readonly saveButton: Locator
  readonly testResult: Locator

  constructor(page: Page) {
    this.page = page
    this.overlay = page.locator('[style*="position: fixed"]').filter({ hasText: '设置' })
    this.panel = this.overlay.locator('div').filter({ has: this.page.locator('h2') }).first()
    this.title = this.overlay.locator('h2', { hasText: '设置' })
    this.closeButton = this.overlay.locator('button', { hasText: 'x' })
    this.saveButton = this.overlay.locator('button', { hasText: /保存设置/ })
    this.testResult = this.overlay.locator('span').last()
  }

  /** Wait until the settings panel is fully loaded. */
  async waitForReady() {
    await this.title.waitFor({ state: 'visible' })
  }

  /** Close the settings panel. */
  async close() {
    await this.closeButton.click()
  }

  /** Close by clicking the overlay background. */
  async closeByOverlay() {
    await this.page.mouse.click(10, 10)
  }

  /** Get the LLM provider dropdown. */
  getLlmProviderSelect(): Locator {
    return this.overlay.locator('select').nth(0)
  }

  /** Get the image provider dropdown. */
  getImageProviderSelect(): Locator {
    return this.overlay.locator('select').nth(1)
  }

  /** Get the video provider dropdown. */
  getVideoProviderSelect(): Locator {
    return this.overlay.locator('select').nth(2)
  }

  /** Select a value from the LLM provider dropdown. */
  async selectLlmProvider(value: string) {
    await this.getLlmProviderSelect().selectOption(value)
  }

  /** Select a value from the image provider dropdown. */
  async selectImageProvider(value: string) {
    await this.getImageProviderSelect().selectOption(value)
  }

  /** Check if a provider-specific config section is visible. */
  async hasSection(titleFragment: string): Promise<boolean> {
    return this.overlay.locator('h3', { hasText: titleFragment }).isVisible()
  }

  /** Get the registered providers list cards. */
  getProviderCards(): Locator {
    return this.overlay.locator('div[style*="display: flex"][style*="justify-content: space-between"]')
  }

  /** Save settings. */
  async save() {
    await this.saveButton.click()
  }

  /** Click a test connection button by its text. */
  async clickTestConnection(buttonText: string) {
    await this.overlay.locator('button', { hasText: buttonText }).click()
  }
}
