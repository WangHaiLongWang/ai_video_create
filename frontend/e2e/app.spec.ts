import { test, expect } from '@playwright/test'
import { TopBarPage, NodePalettePage, CanvasPage, PropertyPanelPage, AgentComposerPage } from './pages'

/**
 * App loading and basic rendering tests.
 * Verifies that all major UI regions render correctly on initial page load.
 */
test.describe('Application Loading', () => {
  test('page loads with correct title', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle('ai_video_create')
  })

  test('app shell renders all major regions', async ({ page }) => {
    await page.goto('/')

    // The root element should contain the app-shell
    const appShell = page.locator('.app-shell')
    await expect(appShell).toBeVisible()
  })

  test('top bar displays brand and workflow name', async ({ page }) => {
    await page.goto('/')

    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Brand title should be visible
    await expect(topBar.brandTitle).toBeVisible()

    // Workflow name should be displayed (default workflow)
    const name = await topBar.getWorkflowName()
    expect(name.length).toBeGreaterThan(0)
  })

  test('top bar shows auto-save status', async ({ page }) => {
    await page.goto('/')

    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await expect(topBar.autoSaveStatus).toBeVisible()
    const text = await topBar.autoSaveStatus.textContent()
    expect(text).toContain('已自动保存')
  })

  test('top bar shows run button when idle', async ({ page }) => {
    await page.goto('/')

    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await expect(topBar.runButton).toBeVisible()
    await expect(topBar.stopButton).not.toBeVisible()
  })

  test('node palette renders with all node kinds', async ({ page }) => {
    await page.goto('/')

    const palette = new NodePalettePage(page)
    await palette.waitForReady()

    // Should have 6 node kinds: textInput, storyboard, textToImage, imageToVideo, videoConcat, output
    const count = await palette.getNodeCount()
    expect(count).toBe(6)

    // Verify specific nodes are present
    await expect(palette.getNodeByLabel('主题输入')).toBeVisible()
    await expect(palette.getNodeByLabel('分镜生成')).toBeVisible()
    await expect(palette.getNodeByLabel('文生图')).toBeVisible()
    await expect(palette.getNodeByLabel('图生视频')).toBeVisible()
    await expect(palette.getNodeByLabel('视频合成')).toBeVisible()
    await expect(palette.getNodeByLabel('成片输出')).toBeVisible()
  })

  test('canvas renders React Flow with default workflow nodes', async ({ page }) => {
    await page.goto('/')

    const canvas = new CanvasPage(page)
    await canvas.waitForReady()

    // Default workflow has 6 nodes
    const nodeCount = await canvas.getNodeCount()
    expect(nodeCount).toBe(6)

    // Should have edges connecting them (5 edges for 6 linear nodes)
    const edgeCount = await canvas.getEdgeCount()
    expect(edgeCount).toBe(5)
  })

  test('property panel shows empty state when no node is selected', async ({ page }) => {
    await page.goto('/')

    const propertyPanel = new PropertyPanelPage(page)
    await propertyPanel.waitForReady()

    // Should show the empty state placeholder
    await expect(propertyPanel.emptyState).toBeVisible()
    await expect(propertyPanel.emptyState).toContainText('选择一个节点')
  })

  test('agent composer is visible with default prompt', async ({ page }) => {
    await page.goto('/')

    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Should be open by default
    expect(await agent.isOpen()).toBe(true)

    // Should have a pre-filled prompt
    const prompt = await agent.getPrompt()
    expect(prompt.length).toBeGreaterThan(0)
  })

  test('canvas controls and minimap are rendered', async ({ page }) => {
    await page.goto('/')

    const canvas = new CanvasPage(page)
    await canvas.waitForReady()

    await expect(canvas.controls).toBeVisible()
    await expect(canvas.miniMap).toBeVisible()
  })

  test('node palette shows connection status', async ({ page }) => {
    await page.goto('/')

    const palette = new NodePalettePage(page)
    await palette.waitForReady()

    const connected = await palette.isConnected()
    expect(connected).toBe(true)
  })
})
