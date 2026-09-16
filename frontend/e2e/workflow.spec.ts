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

  // --- Agent Composer ---

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
