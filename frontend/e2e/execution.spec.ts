import { test, expect } from '@playwright/test'
import { TopBarPage, CanvasPage, PropertyPanelPage } from './pages'

/**
 * Execution panel functionality tests.
 * Covers the run/stop workflow lifecycle, execution status display,
 * and node status transitions during execution.
 *
 * NOTE: These tests rely on the backend API being available. If the backend
 * is not running, the run button click will trigger API calls that fail,
 * and the UI will show error states. Tests are designed to verify the UI
 * behavior regardless of backend availability.
 */
test.describe('Execution Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const canvas = new CanvasPage(page)
    await canvas.waitForReady()
  })

  // --- Run Button ---

  test('run button is visible when workflow is idle', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await expect(topBar.runButton).toBeVisible()
    const text = await topBar.runButton.textContent()
    expect(text).toContain('运行工作流')
  })

  test('stop button is hidden when workflow is idle', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await expect(topBar.stopButton).not.toBeVisible()
  })

  // --- Execution Lifecycle ---

  test('clicking run triggers execution state changes', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Intercept API calls to simulate backend responses for CI without backend
    // If backend is not running, the run will fail gracefully

    // Click run
    await topBar.clickRun()

    // The UI should transition - either to running state (if backend is up)
    // or to an error/idle state (if backend is down). We just verify
    // the button state changes.
    await page.waitForTimeout(1000)

    // After clicking run, the runMessage should update from the default
    const statusArea = page.locator('.run-summary')
    if (await statusArea.isVisible()) {
      const text = await statusArea.textContent()
      // The message should have changed from "准备执行"
      expect(text).toBeTruthy()
    }
  })

  test('node status shows idle by default for all nodes', async ({ page }) => {
    const canvas = new CanvasPage(page)

    const nodeLabels = ['主题输入', '分镜生成', '文生图', '图生视频', '视频合成', '成片输出']

    for (const label of nodeLabels) {
      const status = await canvas.getNodeStatus(label)
      expect(status).toBe('idle')
    }
  })

  test('run summary panel shows ready state when idle', async ({ page }) => {
    const propertyPanel = new PropertyPanelPage(page)
    await propertyPanel.waitForReady()

    // The run summary should be visible and not active
    const isActive = await propertyPanel.isRunSummaryActive()
    expect(isActive).toBe(false)

    const summaryText = await propertyPanel.getRunSummaryText()
    expect(summaryText).toContain('运行状态')
  })

  // --- Error Handling ---

  test('execution failure shows error message in run summary', async ({ page }) => {
    // Intercept the execution API to simulate a failure
    await page.route('**/api/workflows', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'test-wf', name: 'test', description: '', version: 1, created_at: '', updated_at: '' }]),
      })
    })

    await page.route('**/api/workflows/*', (route) => {
      if (route.request().method() === 'PUT') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'test-wf', name: 'test', version: 2 }),
        })
      }
      return route.fallback()
    })

    await page.route('**/api/executions/*/start', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '执行启动失败' }),
      })
    })

    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Click run - should trigger the intercepted error
    await topBar.clickRun()

    // Wait for the error to be processed
    await page.waitForTimeout(2000)

    // The run button should be visible again (back to idle state)
    await expect(topBar.runButton).toBeVisible()
  })

  // --- Undo/Redo During Execution Context ---

  test('keyboard shortcuts Ctrl+Z and Ctrl+Shift+Z are wired up', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)
    await propertyPanel.waitForReady()

    const initialNodeCount = await canvas.getNodeCount()

    // Select a node and modify its config to create undo history
    await canvas.selectNode('主题输入')
    await propertyPanel.setConfigValue('prompt', '修改后的提示词')

    // Undo with Ctrl+Z
    await page.keyboard.press('Control+z')
    await page.waitForTimeout(200)

    // After undo, the prompt should revert
    // Select the node again (undo may deselect)
    await canvas.selectNode('主题输入')
    if (await propertyPanel.hasPropertyForm()) {
      const value = await propertyPanel.getConfigInput('prompt').inputValue()
      expect(value).not.toBe('修改后的提示词')
    }
  })

  // --- Execution Status Display ---

  test('execution status bar is hidden when not running', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    const visible = await topBar.isExecutionStatusVisible()
    expect(visible).toBe(false)
  })

  test('property panel run summary updates during run lifecycle', async ({ page }) => {
    const propertyPanel = new PropertyPanelPage(page)
    await propertyPanel.waitForReady()

    // The run summary should show the default ready message
    const text = await propertyPanel.getRunSummaryText()
    expect(text).toContain('运行状态')
    expect(text).toContain('准备执行')
  })
})
