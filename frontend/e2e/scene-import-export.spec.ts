import { test, expect, type Page } from '@playwright/test'
import { CanvasPage } from './pages'

/**
 * E2E tests for Scene Import/Export (SCENE-010).
 *
 * Covers:
 *   - Group 1: Export Flow (dialog, format selection, download trigger)
 *   - Group 2: Import Flow (dialog, file picker, preview, confirm)
 *   - Group 3: Roundtrip (export -> re-import -> verify parity)
 *   - Group 4: Scene Editor (cards, editing, lock/unlock, read-only)
 */

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'ai-video-create.workflow.v1'

/** Workflow with storyboard nodes — SceneEditor seeds initial scenes from these. */
const WORKFLOW_WITH_STORYBOARD = {
  schemaVersion: '2.0',
  manifestVersion: '1.0',
  id: 'scene-export-test',
  name: '场景导入导出测试',
  nodes: [
    {
      id: 'textInput-1',
      type: 'studio',
      position: { x: 110, y: 150 },
      data: {
        label: '主题输入',
        description: '输入创作主题与要求',
        kind: 'textInput',
        status: 'idle',
        config: { prompt: '雨夜，一名送信人在未来城市穿行' },
      },
    },
    {
      id: 'storyboard-1',
      type: 'studio',
      position: { x: 395, y: 220 },
      data: {
        label: '分镜生成',
        description: '将主题转换为结构化分镜',
        kind: 'storyboard',
        inputType: 'text',
        outputType: 'list<scene>',
        status: 'idle',
        config: {
          provider: 'Mock',
          scenes: 3,
          style: 'cinematic noir',
        },
      },
    },
  ],
  edges: [
    {
      id: 'edge-1',
      source: 'textInput-1',
      sourceHandle: 'text',
      target: 'storyboard-1',
      targetHandle: 'prompt',
      type: 'smoothstep',
      animated: false,
    },
  ],
}

/** A sample scene bundle JSON for import tests. */
const SAMPLE_BUNDLE_JSON = {
  schemaVersion: '1.0',
  storyboardId: '',
  workflowId: '',
  executionId: '',
  title: '导入测试分镜',
  scenes: [
    {
      sceneId: 'import-scene-1',
      index: 0,
      title: '开场镜头',
      narration: '在霓虹闪烁的雨夜中，主角匆匆走过',
      durationSeconds: 6,
      locked: false,
      image: { prompt: 'neon-lit rainy cyberpunk street', negativePrompt: '' },
      video: { prompt: 'rain falling on neon signs', duration: 6, resolution: '480P', ratio: '16:9' },
    },
    {
      sceneId: 'import-scene-2',
      index: 1,
      title: '追逐场景',
      narration: '身后传来脚步声，主角加快了步伐',
      durationSeconds: 4,
      locked: false,
      image: { prompt: 'chase scene dark alley', negativePrompt: '' },
      video: { prompt: 'running through dark alley', duration: 4, resolution: '480P', ratio: '16:9' },
    },
  ],
}

/** Inject workflow into localStorage before page load. */
async function seedWorkflow(page: Page, workflow: typeof WORKFLOW_WITH_STORYBOARD) {
  await page.addInitScript((wf) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(wf))
  }, workflow)
}

/** Make an API request from the browser context. */
async function apiCall(page: Page, path: string, options?: RequestInit) {
  return page.evaluate(
    async ({ path, options }) => {
      const res = await fetch(`/api${path}`, options)
      return res.json()
    },
    { path, options: options ? { ...options, headers: { 'Content-Type': 'application/json' } } : undefined },
  )
}

/** Create a scene draft via the API from the browser context. */
async function createDraftViaAPI(page: Page, workflowId: string, bundle: Record<string, unknown>) {
  return apiCall(page, `/workflows/${workflowId}/scene-drafts`, {
    method: 'POST',
    body: JSON.stringify({ bundle }),
  })
}

/** List scene drafts via the API from the browser context. */
async function listDraftsViaAPI(page: Page, workflowId: string) {
  return apiCall(page, `/workflows/${workflowId}/scene-drafts`)
}

/** Delete a scene draft via the API from the browser context. */
async function deleteDraftViaAPI(page: Page, workflowId: string, draftId: string) {
  return apiCall(page, `/workflows/${workflowId}/scene-drafts/${draftId}`, {
    method: 'DELETE',
  })
}

/** Open the Scene Editor by clicking the FilmStrip icon in the TopBar. */
async function openSceneEditor(page: Page) {
  await page.locator('button[aria-label="场景编辑器"]').click()
  await page.waitForSelector('.scene-editor', { timeout: 5000 })
}

/** Wait for Scene Editor to finish loading (scene cards appear or loading finishes). */
async function waitForSceneEditorReady(page: Page) {
  // Wait for either scene cards to appear OR the loading message to be replaced by content
  await page.waitForFunction(
    () => {
      const cards = document.querySelectorAll('.scene-card')
      const loading = document.querySelector('.se-loading')
      const empty = document.querySelector('.se-empty')
      return cards.length > 0 || empty !== null || (loading === null && document.querySelector('.scene-editor') !== null)
    },
    { timeout: 8000 },
  )
}

/** Check if the backend API is reachable (returns true/false). */
async function isBackendAvailable(page: Page): Promise<boolean> {
  try {
    const result = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/health', { signal: AbortSignal.timeout(2000) })
        return res.ok
      } catch {
        return false
      }
    })
    return result
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Group 1: Export Flow
// ---------------------------------------------------------------------------

test.describe('Group 1 — Export Flow', () => {
  test.beforeEach(async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_STORYBOARD)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)
  })

  test('click Export button opens ExportDialog', async ({ page }) => {
    // Click the export button (Export icon) in the TopBar — does NOT require Scene Editor open
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    // ExportDialog should be visible
    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Should have the export header
    const header = dialog.locator('h3')
    await expect(header).toContainText('导出')
  })

  test('ExportDialog shows format options', async ({ page }) => {
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Should have JSON format radio option
    const jsonRadio = dialog.locator('input[type="radio"][value="json"]')
    await expect(jsonRadio).toBeVisible()

    // Should have markdown format option
    const mdRadio = dialog.locator('input[type="radio"][value="markdown"]')
    await expect(mdRadio).toBeVisible()
  })

  test('ExportDialog shows source options', async ({ page }) => {
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Should have source radio options: 草稿, 执行结果, 合并结果
    const draftRadio = dialog.locator('input[type="radio"][value="draft"]')
    await expect(draftRadio).toBeVisible()

    const execRadio = dialog.locator('input[type="radio"][value="execution"]')
    await expect(execRadio).toBeVisible()

    const mergedRadio = dialog.locator('input[type="radio"][value="merged"]')
    await expect(mergedRadio).toBeVisible()
  })

  test('ExportDialog displays filename preview based on format', async ({ page }) => {
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    const filenameInput = dialog.locator('.export-filename')

    // Default: draft source + JSON format -> scene-bundle.json
    await expect(filenameInput).toHaveValue('scene-bundle.json')

    // Switch format to CSV
    const csvRadio = dialog.locator('input[type="radio"][value="csv"]')
    await csvRadio.click()
    await page.waitForTimeout(200)

    await expect(filenameInput).toHaveValue('scene-bundle.csv')
  })

  test('ExportDialog cancel button closes dialog', async ({ page }) => {
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Click cancel
    await dialog.locator('button', { hasText: '取消' }).click()
    await page.waitForTimeout(300)

    // Dialog should be closed
    await expect(dialog).not.toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// Group 2: Import Flow
// ---------------------------------------------------------------------------

test.describe('Group 2 — Import Flow', () => {
  test.beforeEach(async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_STORYBOARD)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)
  })

  test('click Import button opens ImportDialog', async ({ page }) => {
    // Click the import button (FileArrowUp icon) in the TopBar — does NOT require Scene Editor open
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    // ImportDialog should be visible
    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Should have the import header
    const header = dialog.locator('h3')
    await expect(header).toContainText('导入')
  })

  test('ImportDialog shows file input', async ({ page }) => {
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Should have a file input
    const fileInput = dialog.locator('input[type="file"]')
    await expect(fileInput).toBeVisible()
  })

  test('ImportDialog shows preview after selecting JSON file', async ({ page }) => {
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Create a temporary JSON file and upload it
    const fileInput = dialog.locator('input[type="file"]')

    // Use setInputFiles with a buffer
    const fileContent = JSON.stringify(SAMPLE_BUNDLE_JSON)
    await fileInput.setInputFiles({
      name: 'test-bundle.json',
      mimeType: 'application/json',
      buffer: Buffer.from(fileContent),
    })
    await page.waitForTimeout(500)

    // Preview should show the title and scene count
    const previewTitle = dialog.locator('.import-preview-title')
    await expect(previewTitle).toBeVisible()
    await expect(previewTitle).toContainText('导入测试分镜')

    const previewCount = dialog.locator('.import-preview-count')
    await expect(previewCount).toBeVisible()
    await expect(previewCount).toContainText('2 个场景')
  })

  test('ImportDialog confirm button is enabled after file selection', async ({ page }) => {
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    const fileInput = dialog.locator('input[type="file"]')

    const fileContent = JSON.stringify(SAMPLE_BUNDLE_JSON)
    await fileInput.setInputFiles({
      name: 'test-bundle.json',
      mimeType: 'application/json',
      buffer: Buffer.from(fileContent),
    })
    await page.waitForTimeout(500)

    // Confirm button should be enabled
    const confirmBtn = dialog.locator('button', { hasText: '确认导入' })
    await expect(confirmBtn).toBeEnabled()
  })

  test('ImportDialog cancel button closes dialog without importing', async ({ page }) => {
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    await expect(dialog).toBeVisible()

    // Click cancel
    await dialog.locator('button', { hasText: '取消' }).click()
    await page.waitForTimeout(300)

    // Dialog should be closed
    await expect(dialog).not.toBeVisible()
  })

  test('ImportDialog shows error for invalid JSON', async ({ page }) => {
    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.field-dialog-overlay')
    const fileInput = dialog.locator('input[type="file"]')

    // Upload invalid JSON
    await fileInput.setInputFiles({
      name: 'invalid.json',
      mimeType: 'application/json',
      buffer: Buffer.from('{ "not": "a valid bundle" }'),
    })
    await page.waitForTimeout(500)

    // Error message should appear
    const errorMsg = dialog.locator('.export-dialog-error')
    await expect(errorMsg).toBeVisible()
    await expect(errorMsg).toContainText('无效')
  })
})

// ---------------------------------------------------------------------------
// Group 3: Roundtrip (export -> re-import)
// ---------------------------------------------------------------------------

test.describe('Group 3 — Roundtrip', () => {
  test('export bundle as JSON, re-import, verify scenes match', async ({ page }) => {
    const backendAvailable = await isBackendAvailable(page)
    test.skip(!backendAvailable, 'Backend API not available — skipping roundtrip test')

    await seedWorkflow(page, WORKFLOW_WITH_STORYBOARD)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)

    const workflowId = WORKFLOW_WITH_STORYBOARD.id

    // Step 1: Create a scene draft via API so we have data to export
    const createResult = await createDraftViaAPI(page, workflowId, SAMPLE_BUNDLE_JSON as unknown as Record<string, unknown>)
    const draftId = createResult.draft_id

    // Step 2: Open Export dialog (no Scene Editor needed) and export as JSON
    await page.locator('button[aria-label="导出"]').click()
    await page.waitForTimeout(500)

    const exportDialog = page.locator('.field-dialog-overlay')
    await expect(exportDialog).toBeVisible()

    // Ensure JSON format is selected
    const jsonRadio = exportDialog.locator('input[type="radio"][value="json"]')
    await expect(jsonRadio).toBeChecked()

    // Intercept the download: we capture the blob content by intercepting the download event
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      exportDialog.locator('button', { hasText: '导出' }).click(),
    ])

    // Save the downloaded file to a temp path
    const downloadPath = await download.path()
    expect(downloadPath).toBeTruthy()

    // Read the downloaded content
    const fs = await import('fs')
    const exportedContent = JSON.parse(fs.readFileSync(downloadPath!, 'utf-8'))

    // Verify exported content structure
    expect(exportedContent.schemaVersion).toBe('1.0')
    expect(exportedContent.scenes).toBeDefined()
    expect(exportedContent.scenes.length).toBe(SAMPLE_BUNDLE_JSON.scenes.length)

    // Verify scene titles match
    for (let i = 0; i < SAMPLE_BUNDLE_JSON.scenes.length; i++) {
      expect(exportedContent.scenes[i].title).toBe(SAMPLE_BUNDLE_JSON.scenes[i].title)
      expect(exportedContent.scenes[i].narration).toBe(SAMPLE_BUNDLE_JSON.scenes[i].narration)
      expect(exportedContent.scenes[i].image.prompt).toBe(SAMPLE_BUNDLE_JSON.scenes[i].image.prompt)
    }

    // Step 3: Open Import dialog and import the exported content
    // Wait for export dialog to close (it closes after successful export)
    await page.waitForTimeout(500)

    await page.locator('button[aria-label="导入"]').click()
    await page.waitForTimeout(500)

    const importDialog = page.locator('.field-dialog-overlay')
    await expect(importDialog).toBeVisible()

    // Upload the exported JSON content as a file
    const fileInput = importDialog.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'reimport-bundle.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(exportedContent)),
    })
    await page.waitForTimeout(500)

    // Verify preview
    const previewTitle = importDialog.locator('.import-preview-title')
    await expect(previewTitle).toContainText(SAMPLE_BUNDLE_JSON.title)

    const previewCount = importDialog.locator('.import-preview-count')
    await expect(previewCount).toContainText('2 个场景')

    // Step 4: Confirm import
    const confirmBtn = importDialog.locator('button', { hasText: '确认导入' })
    await expect(confirmBtn).toBeEnabled()
    await confirmBtn.click()
    await page.waitForTimeout(500)

    // Import dialog should close
    await expect(importDialog).not.toBeVisible()

    // Step 5: Verify the imported data by fetching drafts via API
    const drafts = await listDraftsViaAPI(page, workflowId)
    expect(drafts.length).toBeGreaterThanOrEqual(2) // original + imported

    // Cleanup: delete the test drafts
    for (const draft of drafts) {
      await deleteDraftViaAPI(page, workflowId, draft.draft_id)
    }
  })
})

// ---------------------------------------------------------------------------
// Group 4: Scene Editor
// ---------------------------------------------------------------------------

test.describe('Group 4 — Scene Editor', () => {
  test.beforeEach(async ({ page }) => {
    await seedWorkflow(page, WORKFLOW_WITH_STORYBOARD)
    await page.goto('/')
    await new CanvasPage(page).waitForReady()
    await page.waitForTimeout(300)
  })

  test('open Scene Editor — scene cards are displayed', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    // Scene Editor should show scene cards (created from storyboard nodes or empty scenes)
    const sceneCards = page.locator('.scene-card')
    await expect(sceneCards.first()).toBeVisible()

    // Scene count should be displayed in header
    const headerCount = page.locator('.se-header-count')
    await expect(headerCount).toContainText('scenes')
  })

  test('click scene card — expands edit form', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    // Wait for scene cards to appear
    const firstCard = page.locator('.scene-card').first()
    await expect(firstCard).toBeVisible()

    // Click the card header to expand
    const cardHeader = firstCard.locator('.scene-card-header')
    await cardHeader.click()
    await page.waitForTimeout(300)

    // The card should now have the expanded class
    await expect(firstCard).toHaveClass(/scene-card--expanded/)

    // The edit form body should be visible
    const cardBody = firstCard.locator('.scene-card-body')
    await expect(cardBody).toBeVisible()

    // Should show Title, Narration, Duration fields
    const titleField = cardBody.locator('.se-field', { hasText: 'Title' })
    await expect(titleField).toBeVisible()

    const narrationField = cardBody.locator('.se-field', { hasText: 'Narration' })
    await expect(narrationField).toBeVisible()
  })

  test('edit narration text — value updates', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    const firstCard = page.locator('.scene-card').first()
    await firstCard.locator('.scene-card-header').click()
    await page.waitForTimeout(300)

    // Find the narration textarea
    const narrationField = firstCard.locator('.scene-card-body .se-field', { hasText: 'Narration' })
    const textarea = narrationField.locator('textarea')
    await expect(textarea).toBeVisible()

    // Clear and type new narration
    await textarea.clear()
    await textarea.fill('这是一段新的旁白文本')
    await page.waitForTimeout(200)

    // Verify the value was updated
    const newValue = await textarea.inputValue()
    expect(newValue).toBe('这是一段新的旁白文本')
  })

  test('toggle lock on a scene — lock icon appears', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    const firstCard = page.locator('.scene-card').first()
    await firstCard.locator('.scene-card-header').click()
    await page.waitForTimeout(300)

    // Find and click the lock button in the actions bar
    const lockBtn = firstCard.locator('.scene-card-actions-bar button[title="Lock scene"]')
    await expect(lockBtn).toBeVisible()
    await lockBtn.click()
    await page.waitForTimeout(300)

    // The card should now have the locked class
    await expect(firstCard).toHaveClass(/scene-card--locked/)

    // A lock badge should appear in the header
    const lockBadge = firstCard.locator('.scene-card-lock-badge')
    await expect(lockBadge).toBeVisible()

    // The toggle button should now say "Unlock scene"
    const unlockBtn = firstCard.locator('.scene-card-actions-bar button[title="Unlock scene"]')
    await expect(unlockBtn).toBeVisible()
  })

  test('locked scene — fields are read-only (disabled)', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    const firstCard = page.locator('.scene-card').first()
    await firstCard.locator('.scene-card-header').click()
    await page.waitForTimeout(300)

    // Lock the scene
    const lockBtn = firstCard.locator('.scene-card-actions-bar button[title="Lock scene"]')
    await lockBtn.click()
    await page.waitForTimeout(300)

    // Title input should be disabled
    const titleField = firstCard.locator('.scene-card-body .se-field', { hasText: 'Title' })
    const titleInput = titleField.locator('input[type="text"]')
    await expect(titleInput).toBeDisabled()

    // Narration textarea should be disabled
    const narrationField = firstCard.locator('.scene-card-body .se-field', { hasText: 'Narration' })
    const textarea = narrationField.locator('textarea')
    await expect(textarea).toBeDisabled()

    // Duration input should be disabled
    const durationField = firstCard.locator('.scene-card-body .se-field', { hasText: 'Duration (seconds)' })
    const durationInput = durationField.locator('input[type="number"]')
    await expect(durationInput).toBeDisabled()
  })

  test('unlock scene — fields become editable again', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    const firstCard = page.locator('.scene-card').first()
    await firstCard.locator('.scene-card-header').click()
    await page.waitForTimeout(300)

    // Lock then unlock
    const lockBtn = firstCard.locator('.scene-card-actions-bar button[title="Lock scene"]')
    await lockBtn.click()
    await page.waitForTimeout(300)

    const unlockBtn = firstCard.locator('.scene-card-actions-bar button[title="Unlock scene"]')
    await unlockBtn.click()
    await page.waitForTimeout(300)

    // Title input should now be enabled
    const titleField = firstCard.locator('.scene-card-body .se-field', { hasText: 'Title' })
    const titleInput = titleField.locator('input[type="text"]')
    await expect(titleInput).toBeEnabled()

    // Lock badge should be gone
    const lockBadge = firstCard.locator('.scene-card-lock-badge')
    await expect(lockBadge).not.toBeVisible()
  })

  test('Scene Editor close button dismisses the editor', async ({ page }) => {
    await openSceneEditor(page)

    const editor = page.locator('.scene-editor')
    await expect(editor).toBeVisible()

    // Click close button
    await page.locator('.se-close-btn').click()
    await page.waitForTimeout(300)

    // Editor should be gone
    await expect(editor).not.toBeVisible()
  })

  test('Scene Editor shows stats bar with scene count and duration', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    // Stats bar should be visible
    const stats = page.locator('.se-stats')
    await expect(stats).toBeVisible()

    // Should contain scene count
    await expect(stats).toContainText(/scenes/)

    // Should contain total duration
    await expect(stats).toContainText(/total/)
  })

  test('click Add button adds a new empty scene', async ({ page }) => {
    await openSceneEditor(page)
    await waitForSceneEditorReady(page)

    // Count initial scenes
    const initialCount = await page.locator('.scene-card').count()
    expect(initialCount).toBeGreaterThan(0)

    // Click Add button
    await page.locator('.se-add-btn').click()
    await page.waitForTimeout(300)

    // Should have one more scene card
    const newCount = await page.locator('.scene-card').count()
    expect(newCount).toBe(initialCount + 1)

    // The new card should be the last one with default title
    const lastCard = page.locator('.scene-card').last()
    const titleText = lastCard.locator('.scene-card-title-text')
    await expect(titleText).toContainText('Scene')
  })
})
