import type { Locator, Page } from '@playwright/test'

/**
 * Page Object for the PropertyPanel (right sidebar for node configuration).
 * Handles both the empty state and the active node configuration state.
 */
export class PropertyPanelPage {
  readonly page: Page
  readonly panel: Locator
  readonly heading: Locator
  readonly emptyState: Locator
  readonly propertyForm: Locator
  readonly selectedTitle: Locator
  readonly runSummary: Locator

  constructor(page: Page) {
    this.page = page
    this.panel = page.locator('aside.properties')
    this.heading = this.panel.locator('.panel-heading')
    this.emptyState = this.panel.locator('.empty-panel')
    this.propertyForm = this.panel.locator('.property-form')
    this.selectedTitle = this.panel.locator('.selected-title')
    this.runSummary = this.panel.locator('.run-summary')
  }

  /** Wait until the property panel is visible. */
  async waitForReady() {
    await this.panel.waitFor({ state: 'visible' })
  }

  /** Check if the empty state (no node selected) is shown. */
  async isEmpty(): Promise<boolean> {
    return this.emptyState.isVisible()
  }

  /** Check if a property form is shown for a selected node. */
  async hasPropertyForm(): Promise<boolean> {
    return this.propertyForm.isVisible()
  }

  /** Get the label of the currently selected node. */
  async getSelectedNodeLabel(): Promise<string> {
    return (await this.selectedTitle.locator('span').textContent()) ?? ''
  }

  /** Get the kind of the currently selected node. */
  async getSelectedNodeKind(): Promise<string> {
    return (await this.selectedTitle.locator('small').textContent()) ?? ''
  }

  /** Get all config fields in the property form. */
  getConfigFields(): Locator {
    return this.propertyForm.locator('label')
  }

  /** Get a specific config field by its key label text. */
  getConfigField(key: string): Locator {
    return this.propertyForm.locator('label', { hasText: key })
  }

  /** Get the input element within a config field. */
  getConfigInput(key: string): Locator {
    return this.getConfigField(key).locator('input')
  }

  /** Update a text/number config field's value. */
  async setConfigValue(key: string, value: string) {
    const input = this.getConfigInput(key)
    await input.fill(value)
  }

  /** Toggle a boolean config field. */
  async toggleConfig(key: string) {
    const checkbox = this.getConfigField(key).locator('input[type="checkbox"]')
    await checkbox.click()
  }

  /** Check the run summary status text. */
  async getRunSummaryText(): Promise<string> {
    return (await this.runSummary.textContent()) ?? ''
  }

  /** Check if the run summary is in active (running) state. */
  async isRunSummaryActive(): Promise<boolean> {
    const className = await this.runSummary.getAttribute('class')
    return className?.includes('is-active') ?? false
  }

  // --- Field operations ---

  /** The "添加字段" button. */
  get addFieldButton(): Locator {
    return this.propertyForm.locator('button', { hasText: '添加字段' })
  }

  /** Click the "添加字段" button to open the field dialog. */
  async clickAddField() {
    await this.addFieldButton.click()
  }

  /** The FieldEditorDialog overlay (when open). */
  get fieldDialog(): Locator {
    return this.panel.locator('.field-dialog-overlay')
  }

  /** The field dialog title. */
  get fieldDialogTitle(): Locator {
    return this.fieldDialog.locator('h3')
  }

  /** Fill the field dialog ID input. */
  async fillFieldId(id: string) {
    const input = this.fieldDialog.locator('input[placeholder="snake_case_field_id"]')
    await input.fill(id)
  }

  /** Fill the field dialog label input. */
  async fillFieldLabel(label: string) {
    const inputs = this.fieldDialog.locator('label').filter({ hasText: 'Label' }).locator('input')
    await inputs.fill(label)
  }

  /** Save the field dialog. */
  async saveFieldDialog() {
    await this.fieldDialog.locator('button', { hasText: 'Save' }).click()
  }

  /** Cancel the field dialog. */
  async cancelFieldDialog() {
    await this.fieldDialog.locator('button', { hasText: 'Cancel' }).click()
  }

  /** Check if a field with given label is visible in the property panel. */
  async hasField(label: string): Promise<boolean> {
    return this.propertyForm.locator('.prop-field-row', { hasText: label }).isVisible()
  }

  /** Get the input for a field value by field label text. */
  getFieldValueInput(label: string): Locator {
    return this.propertyForm.locator('.prop-field-row', { hasText: label }).locator('input')
  }

  /** Delete a field by clicking its trash button. */
  async deleteFieldByLabel(label: string) {
    const fieldRow = this.propertyForm.locator('.prop-field-row', { hasText: label })
    await fieldRow.locator('button[title="删除"]').click()
  }

  /** Confirm deletion in the confirmation dialog. */
  async confirmDelete() {
    const confirmDialog = this.panel.locator('.field-dialog-overlay')
    await confirmDialog.locator('button', { hasText: '删除' }).click()
  }

  /** Cancel deletion in the confirmation dialog. */
  async cancelDelete() {
    const confirmDialog = this.panel.locator('.field-dialog-overlay')
    await confirmDialog.locator('button', { hasText: '取消' }).click()
  }

  /** Get the PortEditor section. */
  get portEditor(): Locator {
    return this.propertyForm.locator('.port-editor')
  }

  /** Check if port editor is visible with port counts. */
  async hasPortEditor(): Promise<boolean> {
    return this.portEditor.isVisible()
  }
}
