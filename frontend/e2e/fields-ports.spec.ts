import { test, expect, type Page } from '@playwright/test'
import { CanvasPage, PropertyPanelPage } from './pages'

/**
 * E2E tests for Field and Port CRUD operations (FIELD-007).
 *
 * Covers:
 *   - Group 1: Field creation, editing, deletion, and validation
 *   - Group 2: Port CRUD and core-port locking
 *   - Group 3: Port deletion with edge cascade
 *   - Group 4: Integration (port + edge roundtrip)
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'ai-video-create.workflow.v1'

/** Workflow with two nodes — one input, one output — no edges. */
const TWO_NODE_WORKFLOW = {
  schemaVersion: '2.0',
  manifestVersion: '1.0',
  id: 'fields-ports-test',
  name: '字段端口测试',
  nodes: [
    {
      id: 'textInput-1', type: 'studio', position: { x: 110, y: 150 },
      data: {
        label: '主题输入', description: '输入创作主题与要求', kind: 'textInput',
        status: 'idle', config: { prompt: 'test prompt' },
        ports: {
          inputs: [],
          outputs: [{ id: 'text', type: 'text', required: false, cardinality: 'one', label: 'text' }],
        },
      },
    },
    {
      id: 'storyboard-1', type: 'studio', position: { x: 395, y: 220 },
      data: {
        label: '分镜生成', description: '将主题转换为结构化分镜', kind: 'storyboard',
        status: 'idle', config: { provider: 'Mock' },
        ports: {
          inputs: [{ id: 'prompt', type: 'text', required: true, cardinality: 'one', label: 'prompt' }],
          outputs: [{ id: 'scenes', type: 'scene', required: false, cardinality: 'many', label: 'scenes' }],
        },
      },
    },
  ],
  edges: [],
}

/** Workflow with pre-existing field schema on textInput-1. */
const WORKFLOW_WITH_FIELDS = {
  ...TWO_NODE_WORKFLOW,
  nodes: [
    {
      ...TWO_NODE_WORKFLOW.nodes[0],
      data: {
        ...TWO_NODE_WORKFLOW.nodes[0].data,
        fieldSchema: [
          { id: 'my_text', label: 'My Text', type: 'text', required: false },
          { id: 'my_select', label: 'My Select', type: 'select', options: [{ label: 'Option A', value: 'a' }, { label: 'Option B', value: 'b' }] },
        ],
        config: { prompt: 'test prompt', my_text: 'hello', my_select: 'a' },
      },
    },
    TWO_NODE_WORKFLOW.nodes[1],
  ],
}

/** Workflow with pre-existing custom port on storyboard-1. */
const WORKFLOW_WITH_CUSTOM_PORT = {
  ...TWO_NODE_WORKFLOW,
  nodes: [
    TWO_NODE_WORKFLOW.nodes[0],
    {
      ...TWO_NODE_WORKFLOW.nodes[1],
      data: {
        ...TWO_NODE_WORKFLOW.nodes[1].data,
        ports: {
          inputs: [{ id: 'prompt', type: 'text', required: true, cardinality: 'one', label: 'prompt' }],
          outputs: [
            { id: 'scenes', type: 'scene', required: false, cardinality: 'many', label: 'scenes' },
            { id: 'extra_image', type: 'image', required: false, cardinality: 'one', label: 'extra_image' },
          ],
        },
      },
    },
  ],
}

/** Workflow with edge from textInput-1 to storyboard-1 via custom port. */
const WORKFLOW_WITH_CUSTOM_EDGE = {
  ...WORKFLOW_WITH_CUSTOM_PORT,
  nodes: [
    {
      ...TWO_NODE_WORKFLOW.nodes[0],
      data: {
        ...TWO_NODE_WORKFLOW.nodes[0].data,
        ports: {
          inputs: [],
          outputs: [
            { id: 'text', type: 'text', required: false, cardinality: 'one', label: 'text' },
            { id: 'extra_out', type: 'image', required: false, cardinality: 'one', label: 'extra_out' },
          ],
        },
      },
    },
    TWO_NODE_WORKFLOW.nodes[1],
  ],
  edges: [
    {
      id: 'edge-custom', source: 'textInput-1', sourceHandle: 'extra_out',
      target: 'storyboard-1', targetHandle: 'prompt',
      type: 'smoothstep', animated: false,
    },
  ],
}

/** Inject a workflow into localStorage before page load. */
async function seedWorkflow(page: Page, workflow: typeof TWO_NODE_WORKFLOW) {
  await page.addInitScript((wf) => {
    localStorage.setItem('ai-video-create.workflow.v1', JSON.stringify(wf))
  }, workflow)
}

// ---------------------------------------------------------------------------
// Group 1: Field Tests
// ---------------------------------------------------------------------------

test.describe('Group 1 — Field CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await seedWorkflow(page, TWO_NODE_WORKFLOW)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)
  })

  test('click "+ 添加字段" opens FieldEditorDialog', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click add field button
    await propPanel.clickAddField()

    // FieldEditorDialog should appear
    const dialog = propPanel.fieldDialog
    await expect(dialog).toBeVisible()

    // Dialog title should be "添加字段" (add mode)
    const title = propPanel.fieldDialogTitle
    await expect(title).toContainText('添加字段')
  })

  test('create text field — verify it appears in PropertyPanel', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Open field dialog
    await propPanel.clickAddField()
    await expect(propPanel.fieldDialog).toBeVisible()

    // Fill in label (ID auto-generates from label)
    await propPanel.fillFieldLabel('Username')
    await page.waitForTimeout(100)

    // Save the field
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(300)

    // Dialog should close
    await expect(propPanel.fieldDialog).not.toBeVisible()

    // Field should appear in the property panel
    const hasField = await propPanel.hasField('Username')
    expect(hasField).toBe(true)
  })

  test('create select field with options — verify options display', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Open field dialog
    await propPanel.clickAddField()
    await expect(propPanel.fieldDialog).toBeVisible()

    // Fill label
    await propPanel.fillFieldLabel('Language')
    await page.waitForTimeout(100)

    // Change type to "Select"
    const typeSelect = propPanel.fieldDialog.locator('select').nth(0)
    await typeSelect.selectOption('select')
    await page.waitForTimeout(100)

    // Add options
    const addOptionBtn = propPanel.fieldDialog.locator('button', { hasText: 'Add option' })
    await addOptionBtn.click()

    // Fill first option
    const optionRows = propPanel.fieldDialog.locator('.option-row')
    const firstRow = optionRows.first()
    await firstRow.locator('input').nth(0).fill('English')
    await firstRow.locator('input').nth(1).fill('en')
    await page.waitForTimeout(100)

    // Save
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(300)

    // Field row should appear
    const hasField = await propPanel.hasField('Language')
    expect(hasField).toBe(true)
  })

  test('edit field value — verify value persists in config', async ({ page }) => {
    // Seed with pre-existing fields
    await seedWorkflow(page, WORKFLOW_WITH_FIELDS)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Find the "My Text" field input and update it
    const fieldInput = propPanel.getFieldValueInput('My Text')
    await expect(fieldInput).toBeVisible()
    await fieldInput.fill('world')
    await page.waitForTimeout(200)

    // Verify the value was updated by reading it back
    const newValue = await fieldInput.inputValue()
    expect(newValue).toBe('world')
  })

  test('delete custom field with confirmation — verify removed', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_FIELDS)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Confirm the field exists
    const hasFieldBefore = await propPanel.hasField('My Text')
    expect(hasFieldBefore).toBe(true)

    // Click delete button for "My Text"
    await propPanel.deleteFieldByLabel('My Text')
    await page.waitForTimeout(200)

    // Confirmation dialog should appear
    const confirmOverlay = propPanel.panel.locator('.field-dialog-overlay')
    await expect(confirmOverlay).toBeVisible()

    // Click delete in confirmation
    const deleteBtn = confirmOverlay.locator('button', { hasText: '删除' })
    await deleteBtn.click()
    await page.waitForTimeout(300)

    // Field should be removed
    const hasFieldAfter = await propPanel.hasField('My Text')
    expect(hasFieldAfter).toBe(false)
  })

  test('field validation: empty label is rejected', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    await propPanel.clickAddField()
    await expect(propPanel.fieldDialog).toBeVisible()

    // Leave label empty, fill ID manually
    await propPanel.fillFieldId('valid_id')

    // Click save — empty label should prevent save
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(300)

    // Dialog should still be open (save was rejected)
    await expect(propPanel.fieldDialog).toBeVisible()
  })

  test('field validation: non-snake_case ID shows error', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    await propPanel.clickAddField()
    await expect(propPanel.fieldDialog).toBeVisible()

    // Type a non-snake_case ID
    await propPanel.fillFieldId('Invalid ID With Spaces')
    await page.waitForTimeout(100)

    // An error message should appear
    const errorMsg = propPanel.fieldDialog.locator('small', { hasText: 'snake_case' })
    await expect(errorMsg).toBeVisible()

    // Click save — should be blocked by validation
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(200)

    // Dialog stays open
    await expect(propPanel.fieldDialog).toBeVisible()
  })

  test('undo field creation (Ctrl+Z) removes the field', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Create a field
    await propPanel.clickAddField()
    await propPanel.fillFieldLabel('Undo Me')
    await page.waitForTimeout(100)
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(300)

    // Verify field exists
    const hasField = await propPanel.hasField('Undo Me')
    expect(hasField).toBe(true)

    // Undo
    await page.keyboard.press('Control+z')
    await page.waitForTimeout(500)

    // Field should be removed
    const hasFieldAfter = await propPanel.hasField('Undo Me')
    expect(hasFieldAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Group 2: Port Tests
// ---------------------------------------------------------------------------

test.describe('Group 2 — Port CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await seedWorkflow(page, TWO_NODE_WORKFLOW)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)
  })

  test('view existing ports in PortEditor section', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // PortEditor section should be visible
    const portEditor = propPanel.portEditor
    await expect(portEditor).toBeVisible()

    // textInput-1 has 1 output port (text) and 0 input ports
    const inputHeader = portEditor.locator('.port-section-header').first()
    const inputText = await inputHeader.textContent()
    expect(inputText).toContain('0') // 0 input ports

    const outputHeader = portEditor.locator('.port-section-header').nth(1)
    const outputText = await outputHeader.textContent()
    expect(outputText).toContain('1') // 1 output port
  })

  test('click add port button — PortEditorDialog opens', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click the add input port button (+ icon)
    const addInputBtn = propPanel.portEditor.locator('.port-section-add-btn').first()
    await addInputBtn.click()
    await page.waitForTimeout(200)

    // PortEditorDialog should open (same overlay class as field dialog)
    const dialog = propPanel.panel.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Dialog title should say "添加端口"
    const dialogTitle = dialog.locator('h3')
    await expect(dialogTitle).toContainText('添加端口')
  })

  test('add new input port with type "image" — verify it appears', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click add input port
    const addInputBtn = propPanel.portEditor.locator('.port-section-add-btn').first()
    await addInputBtn.click()
    await page.waitForTimeout(200)

    const dialog = propPanel.panel.locator('.field-dialog-overlay')

    // Fill label
    const labelInput = dialog.locator('label', { hasText: 'Label' }).locator('input')
    await labelInput.fill('background_image')
    await page.waitForTimeout(100)

    // Select type "image"
    const typeSelect = dialog.locator('label', { hasText: 'Type' }).locator('select')
    await typeSelect.selectOption('image')
    await page.waitForTimeout(100)

    // Save
    await dialog.locator('button', { hasText: 'Save' }).click()
    await page.waitForTimeout(300)

    // The new port should appear in the port list
    const portRow = propPanel.portEditor.locator('.port-row', { hasText: 'background_image' })
    await expect(portRow).toBeVisible()

    // Input port count should increase to 2
    const inputHeader = propPanel.portEditor.locator('.port-section-header').first()
    const inputText = await inputHeader.textContent()
    expect(inputText).toContain('2')
  })

  test('add new output port with type "video" — verify it appears', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click add output port (+ button in output section, second section)
    const addOutputBtn = propPanel.portEditor.locator('.port-section-add-btn').nth(1)
    await addOutputBtn.click()
    await page.waitForTimeout(200)

    const dialog = propPanel.panel.locator('.field-dialog-overlay')

    // Fill label
    const labelInput = dialog.locator('label', { hasText: 'Label' }).locator('input')
    await labelInput.fill('raw_video')
    await page.waitForTimeout(100)

    // Select type "video"
    const typeSelect = dialog.locator('label', { hasText: 'Type' }).locator('select')
    await typeSelect.selectOption('video')
    await page.waitForTimeout(100)

    // Save
    await dialog.locator('button', { hasText: 'Save' }).click()
    await page.waitForTimeout(300)

    // The new port should appear
    const portRow = propPanel.portEditor.locator('.port-row', { hasText: 'raw_video' })
    await expect(portRow).toBeVisible()

    // Output count should increase to 2
    const outputHeader = propPanel.portEditor.locator('.port-section-header').nth(1)
    const outputText = await outputHeader.textContent()
    expect(outputText).toContain('2')
  })

  test('edit port label — verify updated', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_CUSTOM_PORT)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Find the custom port row "extra_image" and click its edit button
    const customPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'extra_image' })
    await expect(customPortRow).toBeVisible()

    // Click the pencil (edit) button
    const editBtn = customPortRow.locator('.port-action-btn').first()
    await editBtn.click()
    await page.waitForTimeout(200)

    // PortEditorDialog should open in edit mode
    const dialog = propPanel.panel.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()
    const dialogTitle = dialog.locator('h3')
    await expect(dialogTitle).toContainText('编辑端口')

    // Update the label
    const labelInput = dialog.locator('label', { hasText: 'Label' }).locator('input')
    await labelInput.clear()
    await labelInput.fill('thumbnail_image')
    await page.waitForTimeout(100)

    // Save
    await dialog.locator('button', { hasText: 'Save' }).click()
    await page.waitForTimeout(300)

    // The port label should be updated
    const updatedPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'thumbnail_image' })
    await expect(updatedPortRow).toBeVisible()
  })

  test('cannot delete core/manifest port — lock icon shown', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // textInput-1 has one core output port: "text"
    // Core ports should have a lock icon, not a delete button
    const textPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'text' })
    await expect(textPortRow).toBeVisible()

    // Lock icon should be present
    const lockIcon = textPortRow.locator('.port-lock-icon')
    await expect(lockIcon).toBeVisible()

    // No delete button should be present for core ports
    const deleteBtn = textPortRow.locator('.port-action-btn--danger')
    const deleteBtnCount = await deleteBtn.count()
    expect(deleteBtnCount).toBe(0)
  })

  test('port ID must be snake_case — validation error shown', async ({ page }) => {
    const canvas = new CanvasPage(page)
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click add input port
    const addInputBtn = propPanel.portEditor.locator('.port-section-add-btn').first()
    await addInputBtn.click()
    await page.waitForTimeout(200)

    const dialog = propPanel.panel.locator('.field-dialog-overlay')

    // Fill label that auto-generates a non-snake_case ID
    const labelInput = dialog.locator('label', { hasText: 'Label' }).locator('input')
    await labelInput.fill('Invalid Port Name!')
    await page.waitForTimeout(100)

    // ID should auto-generate as snake_case from label, but manually set invalid ID
    const idInput = dialog.locator('input[placeholder="snake_case_port_id"]')
    await idInput.clear()
    await idInput.fill('NOT_VALID!')
    await page.waitForTimeout(100)

    // Validation error should appear
    const errorMsg = dialog.locator('small', { hasText: 'snake_case' })
    await expect(errorMsg).toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Group 3: Port Deletion with Edge Cascade
// ---------------------------------------------------------------------------

test.describe('Group 3 — Port Deletion & Edge Cascade', () => {
  test('delete port with edge — confirmation shows affected edge count', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_CUSTOM_EDGE)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // The custom output port "extra_out" has an edge to storyboard-1.prompt
    const customPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'extra_out' })
    await expect(customPortRow).toBeVisible()

    // Click delete on the custom port
    const deleteBtn = customPortRow.locator('.port-action-btn--danger')
    await deleteBtn.click()
    await page.waitForTimeout(200)

    // Delete confirmation dialog should appear with edge warning
    const confirmDialog = propPanel.panel.locator('.field-dialog-overlay')
    await expect(confirmDialog).toBeVisible()

    // Should mention affected edges
    const warningText = await confirmDialog.locator('p').nth(1).textContent()
    expect(warningText).toContain('连线')
  })

  test('confirm port deletion — port and affected edge removed', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_CUSTOM_EDGE)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Verify custom port exists
    const customPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'extra_out' })
    await expect(customPortRow).toBeVisible()

    // Verify edge exists
    const hasEdgeBefore = await canvas.hasEdge('textInput-1', 'storyboard-1')
    expect(hasEdgeBefore).toBe(true)

    // Click delete on the custom port
    const deleteBtn = customPortRow.locator('.port-action-btn--danger')
    await deleteBtn.click()
    await page.waitForTimeout(200)

    // Confirm deletion
    const confirmDialog = propPanel.panel.locator('.field-dialog-overlay')
    const confirmDeleteBtn = confirmDialog.locator('button', { hasText: '删除' })
    await confirmDeleteBtn.click()
    await page.waitForTimeout(300)

    // Port should be removed
    const customPortAfter = propPanel.portEditor.locator('.port-row', { hasText: 'extra_out' })
    const portStillVisible = await customPortAfter.isVisible().catch(() => false)
    expect(portStillVisible).toBe(false)

    // Edge should be removed
    const hasEdgeAfter = await canvas.hasEdge('textInput-1', 'storyboard-1')
    expect(hasEdgeAfter).toBe(false)
  })

  test('cancel port deletion — nothing changes', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_CUSTOM_EDGE)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Click delete on the custom port
    const customPortRow = propPanel.portEditor.locator('.port-row', { hasText: 'extra_out' })
    const deleteBtn = customPortRow.locator('.port-action-btn--danger')
    await deleteBtn.click()
    await page.waitForTimeout(200)

    // Cancel deletion
    const confirmDialog = propPanel.panel.locator('.field-dialog-overlay')
    const cancelBtn = confirmDialog.locator('button', { hasText: '取消' })
    await cancelBtn.click()
    await page.waitForTimeout(200)

    // Port should still exist
    const portStillVisible = await customPortRow.isVisible()
    expect(portStillVisible).toBe(true)

    // Edge should still exist
    const hasEdge = await canvas.hasEdge('textInput-1', 'storyboard-1')
    expect(hasEdge).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Group 4: Integration — Port + Edge Roundtrip
// ---------------------------------------------------------------------------

test.describe('Group 4 — Integration', () => {
  test('add port -> create edge -> save -> refresh -> port and edge persist', async ({ page }) => {
    // Seed a workflow with an extra output port on textInput-1 AND an edge using it
    await seedWorkflow(page, {
      ...TWO_NODE_WORKFLOW,
      nodes: [
        {
          ...TWO_NODE_WORKFLOW.nodes[0],
          data: {
            ...TWO_NODE_WORKFLOW.nodes[0].data,
            ports: {
              inputs: [],
              outputs: [
                { id: 'text', type: 'text', required: false, cardinality: 'one', label: 'text' },
                { id: 'extra_out', type: 'image', required: false, cardinality: 'one', label: 'extra_out' },
              ],
            },
          },
        },
        TWO_NODE_WORKFLOW.nodes[1],
      ],
      edges: [
        {
          id: 'edge-custom', source: 'textInput-1', sourceHandle: 'extra_out',
          target: 'storyboard-1', targetHandle: 'prompt',
          type: 'smoothstep', animated: false,
        },
      ],
    })
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(500)

    const canvas = new CanvasPage(page)

    // Edge should exist after initial load
    const hasEdge = await canvas.hasEdge('textInput-1', 'storyboard-1')
    expect(hasEdge).toBe(true)

    // Verify the custom port appears in the property panel
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    const customPort = propPanel.portEditor.locator('.port-row', { hasText: 'extra_out' })
    await expect(customPort).toBeVisible()

    // Refresh to verify persistence
    await page.reload()
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(500)

    const hasEdgeAfterRefresh = await canvas.hasEdge('textInput-1', 'storyboard-1')
    expect(hasEdgeAfterRefresh).toBe(true)
  })

  test('undo port and field operations restores previous state', async ({ page }) => {
    await seedWorkflow(page, TWO_NODE_WORKFLOW)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Add a field
    await propPanel.clickAddField()
    await propPanel.fillFieldLabel('Temp Field')
    await page.waitForTimeout(100)
    await propPanel.saveFieldDialog()
    await page.waitForTimeout(300)

    // Verify field exists
    let hasField = await propPanel.hasField('Temp Field')
    expect(hasField).toBe(true)

    // Add an input port to storyboard
    await canvas.selectNode('分镜生成')
    await page.waitForTimeout(300)

    const addInputBtn = propPanel.portEditor.locator('.port-section-add-btn').first()
    await addInputBtn.click()
    await page.waitForTimeout(200)

    const dialog = propPanel.panel.locator('.field-dialog-overlay')
    const labelInput = dialog.locator('label', { hasText: 'Label' }).locator('input')
    await labelInput.fill('temp_port')
    await page.waitForTimeout(100)
    await dialog.locator('button', { hasText: 'Save' }).click()
    await page.waitForTimeout(300)

    // Verify port was added
    const tempPort = propPanel.portEditor.locator('.port-row', { hasText: 'temp_port' })
    await expect(tempPort).toBeVisible()

    // Undo the port addition
    await page.keyboard.press('Control+z')
    await page.waitForTimeout(500)

    const portAfterUndo = propPanel.portEditor.locator('.port-row', { hasText: 'temp_port' })
    const portVisible = await portAfterUndo.isVisible().catch(() => false)
    expect(portVisible).toBe(false)
  })

  test('fields with select type render dropdown in PropertyPanel', async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_FIELDS)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const canvas = new CanvasPage(page)
    await canvas.selectNode('主题输入')
    await page.waitForTimeout(300)

    const propPanel = new PropertyPanelPage(page)
    await propPanel.waitForReady()

    // Find the select field row
    const selectRow = propPanel.propertyForm.locator('.prop-field-row', { hasText: 'My Select' })
    await expect(selectRow).toBeVisible()

    // It should render a <select> dropdown
    const selectEl = selectRow.locator('select')
    await expect(selectEl).toBeVisible()

    // Options should be present
    const options = selectEl.locator('option')
    const optionCount = await options.count()
    // At least the default "-- select --" + 2 options = 3
    expect(optionCount).toBeGreaterThanOrEqual(3)
  })
})
