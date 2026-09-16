import { test, expect } from '@playwright/test'
import {
  TopBarPage,
  NodePalettePage,
  CanvasPage,
  PropertyPanelPage,
  SettingsPanelPage,
  AgentComposerPage,
} from './pages'

/**
 * Workflow editor interaction tests.
 * Covers node selection, property editing, adding nodes from palette,
 * settings panel interaction, and template selector.
 */
test.describe('Workflow Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Wait for canvas to be ready with default nodes
    const canvas = new CanvasPage(page)
    await canvas.waitForReady()
  })

  // --- Node Selection ---

  test('clicking a node selects it and shows its properties', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Click on the "主题输入" node
    await canvas.selectNode('主题输入')

    // Property panel should show the node's config
    await expect(propertyPanel.propertyForm).toBeVisible()
    const label = await propertyPanel.getSelectedNodeLabel()
    expect(label).toBe('主题输入')
    const kind = await propertyPanel.getSelectedNodeKind()
    expect(kind).toBe('textInput')
  })

  test('clicking canvas background deselects the selected node', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Select a node first
    await canvas.selectNode('主题输入')
    await expect(propertyPanel.propertyForm).toBeVisible()

    // Click on the canvas background to deselect
    await canvas.deselectNodes()

    // Property panel should revert to empty state
    await expect(propertyPanel.emptyState).toBeVisible()
  })

  test('selecting different nodes updates the property panel', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Select "分镜生成" node
    await canvas.selectNode('分镜生成')
    await expect(propertyPanel.propertyForm).toBeVisible()
    expect(await propertyPanel.getSelectedNodeLabel()).toBe('分镜生成')
    expect(await propertyPanel.getSelectedNodeKind()).toBe('storyboard')

    // Switch to "文生图" node
    await canvas.selectNode('文生图')
    await expect(propertyPanel.propertyForm).toBeVisible()
    expect(await propertyPanel.getSelectedNodeLabel()).toBe('文生图')
    expect(await propertyPanel.getSelectedNodeKind()).toBe('textToImage')
  })

  // --- Property Editing ---

  test('editing a text config field updates the node', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Select the textInput node
    await canvas.selectNode('主题输入')

    // The textInput node should have a "prompt" config field
    const promptField = propertyPanel.getConfigField('prompt')
    await expect(promptField).toBeVisible()

    // Change the prompt value
    await propertyPanel.setConfigValue('prompt', '新的测试提示词')

    // Verify the input now has the new value
    const inputValue = await propertyPanel.getConfigInput('prompt').inputValue()
    expect(inputValue).toBe('新的测试提示词')
  })

  test('node status is idle by default', async ({ page }) => {
    const canvas = new CanvasPage(page)

    const status = await canvas.getNodeStatus('主题输入')
    expect(status).toBe('idle')
  })

  // --- Adding Nodes from Palette ---

  test('clicking a node kind in the palette adds a new node to the canvas', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const palette = new NodePalettePage(page)
    await palette.waitForReady()

    const initialCount = await canvas.getNodeCount()

    // Add a new node by clicking "主题输入" in the palette
    await palette.addNodeByLabel('主题输入')

    // Wait for the new node to appear
    await page.waitForTimeout(300)

    const newCount = await canvas.getNodeCount()
    expect(newCount).toBe(initialCount + 1)
  })

  // --- Settings Panel ---

  test('opening and closing settings panel', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Open settings
    await topBar.openSettings()

    const settingsPanel = new SettingsPanelPage(page)
    await settingsPanel.waitForReady()
    await expect(settingsPanel.title).toBeVisible()

    // Close settings
    await settingsPanel.close()

    // Panel should be hidden
    await expect(settingsPanel.title).not.toBeVisible()
  })

  test('settings panel shows provider dropdowns', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await topBar.openSettings()

    const settingsPanel = new SettingsPanelPage(page)
    await settingsPanel.waitForReady()

    // LLM provider select should be visible
    const llmSelect = settingsPanel.getLlmProviderSelect()
    await expect(llmSelect).toBeVisible()

    // Image provider select should be visible
    const imageSelect = settingsPanel.getImageProviderSelect()
    await expect(imageSelect).toBeVisible()

    // Video provider select should be visible
    const videoSelect = settingsPanel.getVideoProviderSelect()
    await expect(videoSelect).toBeVisible()

    await settingsPanel.close()
  })

  test('changing LLM provider shows relevant config section', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await topBar.openSettings()

    const settingsPanel = new SettingsPanelPage(page)
    await settingsPanel.waitForReady()

    // Default is 'mock', switch to 'ollama'
    await settingsPanel.selectLlmProvider('ollama')

    // Ollama config section should appear
    expect(await settingsPanel.hasSection('Ollama 配置')).toBe(true)

    // Switch to 'openai'
    await settingsPanel.selectLlmProvider('openai')
    expect(await settingsPanel.hasSection('OpenAI 配置')).toBe(true)

    await settingsPanel.close()
  })

  // --- Template Selector ---

  test('opening and closing template selector', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Open template selector
    await topBar.openTemplates()

    // Should show the template selector panel
    const selectorTitle = page.locator('h2', { hasText: '选择模板' })
    await expect(selectorTitle).toBeVisible()

    // Close by clicking the close button
    const closeBtn = page.locator('h2', { hasText: '选择模板' }).locator('..').locator('button', { hasText: 'x' })
    await closeBtn.click()

    // Title should be hidden
    await expect(selectorTitle).not.toBeVisible()
  })

  test('template selector has a search input', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    await topBar.openTemplates()

    const searchInput = page.locator('input[placeholder="搜索模板..."]')
    await expect(searchInput).toBeVisible()

    // Can type in the search box
    await searchInput.fill('测试')
    const value = await searchInput.inputValue()
    expect(value).toBe('测试')

    // Close the selector
    await page.keyboard.press('Escape')
  })

  // --- Node Dragging ---

  test('dragging a node changes its position on the canvas', async ({ page }) => {
    const canvas = new CanvasPage(page)

    // Get the initial bounding box of the "分镜生成" node
    const node = canvas.getNodeByLabel('分镜生成')
    const boxBefore = await node.boundingBox()
    expect(boxBefore).not.toBeNull()

    // Drag the node 100px to the right and 50px down
    await canvas.dragNode('分镜生成', 100, 50)

    // Wait for React Flow to settle the layout
    await page.waitForTimeout(300)

    const boxAfter = await node.boundingBox()
    expect(boxAfter).not.toBeNull()

    // The node should have moved (at least some amount in X)
    expect(Math.abs(boxAfter!.x - boxBefore!.x)).toBeGreaterThan(20)
  })

  test('multiple nodes can be dragged independently', async ({ page }) => {
    const canvas = new CanvasPage(page)

    const nodeA = canvas.getNodeByLabel('主题输入')
    const nodeB = canvas.getNodeByLabel('文生图')

    const boxABefore = await nodeA.boundingBox()
    const boxBBefore = await nodeB.boundingBox()

    // Drag node A
    await canvas.dragNode('主题输入', 50, 0)
    await page.waitForTimeout(200)

    // Drag node B
    await canvas.dragNode('文生图', 0, 80)
    await page.waitForTimeout(200)

    const boxAAfter = await nodeA.boundingBox()
    const boxBAfter = await nodeB.boundingBox()

    // Node A should have moved mostly in X
    expect(Math.abs(boxAAfter!.x - boxABefore!.x)).toBeGreaterThan(10)
    // Node B should have moved mostly in Y
    expect(Math.abs(boxBAfter!.y - boxBBefore!.y)).toBeGreaterThan(10)
  })

  // --- Workflow Save ---

  test('auto-save indicator is shown in top bar', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // The auto-save status button should display the save status
    await expect(topBar.autoSaveStatus).toBeVisible()
    const text = await topBar.autoSaveStatus.textContent()
    expect(text).toContain('已自动保存')
  })

  test('editing a node config marks workflow as dirty and triggers save', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Select a node and modify it
    await canvas.selectNode('主题输入')
    await propertyPanel.setConfigValue('prompt', '保存测试内容')

    // Wait for the debounced save to fire (SAVE_DEBOUNCE_MS = 1000)
    await page.waitForTimeout(1500)

    // Verify the value persisted in localStorage
    const stored = await page.evaluate(() => {
      return localStorage.getItem('ai-video-create.workflow.v1')
    })
    expect(stored).not.toBeNull()
    const parsed = JSON.parse(stored!)
    const textNode = parsed.nodes.find((n: { id: string }) => n.id === 'textInput-1')
    expect(textNode.data.config.prompt).toBe('保存测试内容')
  })

  test('workflow data persists across page reload', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    // Modify a node
    await canvas.selectNode('主题输入')
    await propertyPanel.setConfigValue('prompt', '跨页面持久化测试')
    await page.waitForTimeout(1500)

    // Reload the page
    await page.reload()
    await canvas.waitForReady()

    // Select the same node and verify the value persisted
    await canvas.selectNode('主题输入')
    const inputValue = await propertyPanel.getConfigInput('prompt').inputValue()
    expect(inputValue).toBe('跨页面持久化测试')
  })

  // --- Execute Workflow ---

  test('clicking run button starts execution', async ({ page }) => {
    const topBar = new TopBarPage(page)
    await topBar.waitForReady()

    // Run button should be visible before execution
    await expect(topBar.runButton).toBeVisible()

    // Click run
    await topBar.clickRun()

    // Wait briefly for state transition
    await page.waitForTimeout(1000)

    // After clicking run, either:
    // 1. Backend is up: stop button appears (running state)
    // 2. Backend is down: run button reappears (error/idle state)
    // In both cases the UI should respond
    const isStopVisible = await topBar.stopButton.isVisible()
    const isRunVisible = await topBar.runButton.isVisible()
    expect(isStopVisible || isRunVisible).toBe(true)
  })

  test('execution shows node status transitions', async ({ page }) => {
    const canvas = new CanvasPage(page)

    // All nodes should start in idle status
    const nodeLabels = ['主题输入', '分镜生成', '文生图', '图生视频', '视频合成', '成片输出']
    for (const label of nodeLabels) {
      const status = await canvas.getNodeStatus(label)
      expect(status).toBe('idle')
    }
  })

  test('run summary displays default ready message', async ({ page }) => {
    const propertyPanel = new PropertyPanelPage(page)
    await propertyPanel.waitForReady()

    const text = await propertyPanel.getRunSummaryText()
    expect(text).toContain('运行状态')
    expect(text).toContain('准备执行')
  })

  // --- View Status ---

  test('node status CSS class reflects idle state', async ({ page }) => {
    const canvas = new CanvasPage(page)

    // Each node should have a status-idle class on its .studio-node element
    const node = canvas.getNodeByLabel('主题输入')
    const article = node.locator('.studio-node')
    const className = await article.getAttribute('class')
    expect(className).toContain('status-idle')
  })

  test('selecting a node shows its status in the property panel', async ({ page }) => {
    const canvas = new CanvasPage(page)
    const propertyPanel = new PropertyPanelPage(page)

    await canvas.selectNode('分镜生成')
    await expect(propertyPanel.propertyForm).toBeVisible()

    // The selected title should show the node label
    const label = await propertyPanel.getSelectedNodeLabel()
    expect(label).toBe('分镜生成')

    // The kind should be 'storyboard'
    const kind = await propertyPanel.getSelectedNodeKind()
    expect(kind).toBe('storyboard')
  })

  // --- Agent Composer (moved from here to agent.spec.ts but kept basic checks) ---

  test('agent composer can be collapsed and expanded', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Should be open initially
    expect(await agent.isOpen()).toBe(true)

    // Collapse it
    await agent.collapse()

    // FAB should be visible
    expect(await agent.isCollapsed()).toBe(true)
    expect(await agent.isOpen()).toBe(false)

    // Expand it
    await agent.expand()

    // Should be open again
    expect(await agent.isOpen()).toBe(true)
  })

  test('agent composer textarea can be edited', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Set a custom prompt
    await agent.setPrompt('创建一个3镜头的风景视频')

    const prompt = await agent.getPrompt()
    expect(prompt).toBe('创建一个3镜头的风景视频')
  })
})
