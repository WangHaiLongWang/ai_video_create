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

  // --- Modify mode (MOD-R3-004) ---
  readonly modifyToggleButton: Locator
  readonly modifyTextarea: Locator
  readonly modifyButton: Locator
  readonly patchSection: Locator
  readonly diffSection: Locator
  readonly moduleDiffsSection: Locator
  readonly compiledWorkflowSection: Locator
  readonly destructiveBanner: Locator
  readonly destructiveConfirm: Locator
  readonly confirmDestructiveButton: Locator
  readonly cancelDestructiveButton: Locator
  readonly successBanner: Locator

  constructor(page: Page) {
    this.page = page
    this.section = page.locator('section.agent-composer')
    this.title = this.section.locator('.agent-title')
    this.textarea = this.section.locator('textarea')
    // Scope to the generate input only — modify mode adds a second .agent-input.
    this.generateButton = this.section.locator('.agent-input:not(.agent-modify-input) button')
    this.previewSection = this.section.locator('.agent-preview')
    this.applyButton = this.previewSection.locator('button', { hasText: '应用' })
    this.cancelButton = this.previewSection.locator('button', { hasText: '取消' })
    this.errorMessage = this.section.locator('.agent-error')
    this.collapseButton = this.title.locator('button', { hasText: '收起' })
    this.fabButton = page.locator('button.agent-fab')

    this.modifyToggleButton = this.section.locator('.agent-modify-toggle button')
    this.modifyTextarea = this.section.locator('.agent-modify-input textarea')
    this.modifyButton = this.section.locator('.agent-modify-input button')
    this.patchSection = this.previewSection.locator('.agent-preview-section', {
      hasText: '变更内容（增量 Diff）',
    })
    this.diffSection = this.previewSection.locator('.agent-preview-section', {
      hasText: '差异文本',
    })
    this.moduleDiffsSection = this.previewSection.locator('.agent-preview-section', {
      hasText: '模块变更',
    })
    this.compiledWorkflowSection = this.previewSection.locator('.agent-preview-section', {
      hasText: '编译后工作流',
    })
    this.destructiveBanner = this.previewSection.locator('.agent-destructive-warning', {
      hasText: '破坏性变更',
    })
    this.destructiveConfirm = this.previewSection.locator(
      '.agent-destructive-confirm[role="alertdialog"]',
    )
    this.confirmDestructiveButton = this.destructiveConfirm.locator('button', {
      hasText: '确认删除并应用',
    })
    this.cancelDestructiveButton = this.destructiveConfirm.locator('button', { hasText: '取消' })
    this.successBanner = this.section.locator('.agent-success-banner')
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

  // --- Modify mode (MOD-R3-004) ---

  /** Open modify mode ("修改现有工作流"). */
  async enterModifyMode() {
    await this.modifyToggleButton.click()
    await this.modifyTextarea.waitFor({ state: 'visible' })
  }

  /** Leave modify mode (toggle text becomes "取消修改"). */
  async exitModifyMode() {
    await this.modifyToggleButton.click()
    await this.modifyTextarea.waitFor({ state: 'hidden' })
  }

  /** Fill the modify instruction textarea. */
  async setModifyInstruction(text: string) {
    await this.modifyTextarea.fill(text)
  }

  /** Submit the modify instruction ("修改" button). */
  async submitModify() {
    await this.modifyButton.click()
  }

  /** True when the incremental patch preview is the primary view. */
  async hasPatchPreview(): Promise<boolean> {
    return this.patchSection.isVisible()
  }

  /** Human-readable diff text (preview.diff). */
  async getDiffText(): Promise<string> {
    return (await this.diffSection.locator('pre').textContent()) ?? ''
  }

  /** Rows rendered from preview.patch (添加/删除/修改节点、连线). */
  async getPatchItemTexts(): Promise<string[]> {
    return this.patchSection.locator('.agent-patch-item').allTextContents()
  }

  /** Module diff entries (preview.module_diffs). */
  async getModuleDiffTexts(): Promise<string[]> {
    return this.moduleDiffsSection.locator('.agent-module-diff').allTextContents()
  }

  /** Intent-preview moduleId@moduleVersion chips. */
  async getIntentModuleChips(): Promise<string[]> {
    return this.previewSection.locator('.agent-intent-module').allTextContents()
  }

  /** configOverride rows in the intent preview ("覆盖 …"). */
  async getIntentOverrideTexts(): Promise<string[]> {
    return this.previewSection.locator('.agent-intent-override').allTextContents()
  }

  /** Destructive banner ("此操作包含删除（破坏性变更）…"). */
  async hasDestructiveBanner(): Promise<boolean> {
    return this.destructiveBanner.isVisible()
  }

  /** Open the destructive confirm panel via "确认应用". */
  async openDestructiveConfirm() {
    await this.applyButton.click()
    await this.destructiveConfirm.waitFor({ state: 'visible' })
  }

  /** Whether the confirm alertdialog is showing. */
  async isDestructiveConfirmVisible(): Promise<boolean> {
    return this.destructiveConfirm.isVisible()
  }

  /** Deletion list rendered inside the confirm alertdialog. */
  async getDestructiveConfirmListTexts(): Promise<string[]> {
    return this.destructiveConfirm.locator('.agent-patch-item').allTextContents()
  }

  /** Cancel the destructive confirm (nothing is applied). */
  async cancelDestructiveConfirm() {
    await this.cancelDestructiveButton.click()
    await this.destructiveConfirm.waitFor({ state: 'hidden' })
  }

  /** Confirm and apply the destructive patch. */
  async confirmDestructiveApply() {
    await this.confirmDestructiveButton.click()
  }

  /** Apply a non-destructive preview ("确认应用"). */
  async applyPreviewAndWait() {
    await this.applyButton.click()
    await this.successBanner.waitFor({ state: 'visible' })
  }
}
