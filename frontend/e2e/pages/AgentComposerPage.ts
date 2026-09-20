import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the AgentComposer (bottom-left overlay for AI-assisted workflow creation).
 * Covers prompt input, preview generation, and apply/cancel actions.
 */
export class AgentComposerPage {
  readonly page: Page
  readonly section: Locator
  readonly title: Locator
  readonly textarea: Locator
  readonly generateButton: Locator
  readonly previewSection: Locator
  readonly applyButton: Locator
  readonly cancelButton: Locator
  readonly errorMessage: Locator
  readonly collapseButton: Locator
  readonly fabButton: Locator

  constructor(page: Page) {
    this.page = page
    this.section = page.locator('section.agent-composer')
    this.title = this.section.locator('.agent-title')
    this.textarea = this.section.locator('textarea')
    this.generateButton = this.section.locator('.agent-input button')
    this.previewSection = this.section.locator('.agent-preview')
    this.applyButton = this.previewSection.locator('button', { hasText: '应用' })
    this.cancelButton = this.previewSection.locator('button', { hasText: '取消' })
    this.errorMessage = this.section.locator('.agent-error')
    this.collapseButton = this.title.locator('button', { hasText: '收起' })
    this.fabButton = page.locator('button.agent-fab')
  }

  /** Wait until the agent composer is visible. */
  async waitForReady() {
    await this.section.waitFor({ state: 'visible' })
  }

  /** Check if the agent composer is currently open. */
  async isOpen(): Promise<boolean> {
    return this.section.isVisible()
  }

  /** Check if the FAB (collapsed state) is visible. */
  async isCollapsed(): Promise<boolean> {
    return this.fabButton.isVisible()
  }

  /** Get the current prompt text. */
  async getPrompt(): Promise<string> {
    return (await this.textarea.inputValue()) ?? ''
  }

  /** Set the prompt text. */
  async setPrompt(text: string) {
    await this.textarea.fill(text)
  }

  /** Click the generate preview button. */
  async clickGenerate() {
    await this.generateButton.click()
  }

  /** Check if the generate button is in loading state. */
  async isGenerating(): Promise<boolean> {
    return (await this.generateButton.textContent())?.includes('生成中') ?? false
  }

  /** Check if the preview section is visible. */
  async hasPreview(): Promise<boolean> {
    return this.previewSection.isVisible()
  }

  /** Apply the generated preview. */
  async applyPreview() {
    await this.applyButton.click()
  }

  /** Cancel the generated preview. */
  async cancelPreview() {
    await this.cancelButton.click()
  }

  /** Collapse the agent composer. */
  async collapse() {
    await this.collapseButton.click()
  }

  /** Expand from FAB state. */
  async expand() {
    await this.fabButton.click()
  }

  /** Check if an error message is displayed. */
  async hasError(): Promise<boolean> {
    return this.errorMessage.isVisible()
  }

  /** Get the error message text. */
  async getErrorText(): Promise<string> {
    return (await this.errorMessage.textContent()) ?? ''
  }
}
