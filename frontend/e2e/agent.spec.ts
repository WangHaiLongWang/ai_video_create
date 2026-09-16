import { test, expect } from '@playwright/test'
import { AgentComposerPage, CanvasPage } from './pages'

/**
 * Agent Composer feature tests.
 * Covers the AI-assisted workflow generation panel:
 * prompt input, generation trigger, preview display, apply/cancel actions.
 *
 * NOTE: These tests rely on the backend API for /api/agent/* endpoints.
 * When the backend is unavailable, API calls will fail and the UI will
 * show error states. Tests verify UI behavior in both success and failure paths.
 */
test.describe('Agent Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const canvas = new CanvasPage(page)
    await canvas.waitForReady()
  })

  // --- Panel Visibility ---

  test('agent composer panel is visible on page load', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    expect(await agent.isOpen()).toBe(true)
    await expect(agent.section).toBeVisible()
  })

  test('agent composer shows title and textarea', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    await expect(agent.title).toBeVisible()
    const titleText = await agent.title.textContent()
    expect(titleText).toContain('Workflow Agent')

    await expect(agent.textarea).toBeVisible()
    await expect(agent.generateButton).toBeVisible()
  })

  test('agent composer has a default prompt pre-filled', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    const prompt = await agent.getPrompt()
    expect(prompt.length).toBeGreaterThan(0)
  })

  test('agent composer can be collapsed to FAB', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    expect(await agent.isOpen()).toBe(true)

    // Collapse
    await agent.collapse()

    // FAB should appear, panel should be hidden
    expect(await agent.isCollapsed()).toBe(true)
    expect(await agent.isOpen()).toBe(false)
  })

  test('clicking FAB re-expands the agent composer', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Collapse then expand
    await agent.collapse()
    expect(await agent.isCollapsed()).toBe(true)

    await agent.expand()
    expect(await agent.isOpen()).toBe(true)
    await expect(agent.textarea).toBeVisible()
  })

  // --- Prompt Editing ---

  test('textarea can be edited with custom prompt', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    await agent.setPrompt('创建一个3镜头的风景视频')

    const prompt = await agent.getPrompt()
    expect(prompt).toBe('创建一个3镜头的风景视频')
  })

  test('generate button text changes during loading', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Initially should show "生成预览" (not generating)
    const initialText = await agent.generateButton.textContent()
    expect(initialText).toContain('生成预览')
    expect(initialText).not.toContain('生成中')
  })

  // --- Generate Workflow ---

  test('clicking generate with empty prompt does nothing', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Clear the prompt
    await agent.setPrompt('')

    // Click generate - should be a no-op
    await agent.clickGenerate()
    await page.waitForTimeout(500)

    // No preview should appear
    expect(await agent.hasPreview()).toBe(false)
  })

  test('clicking generate triggers API call', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Set up API interception
    let generateCalled = false
    await page.route('**/api/agent/generate-preview', (route) => {
      generateCalled = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'agent-generated',
            name: 'AI 生成工作流',
            nodes: [
              {
                id: 'textInput-1',
                type: 'studio',
                position: { x: 110, y: 150 },
                data: {
                  label: '主题输入',
                  description: '输入创作主题与要求',
                  kind: 'textInput',
                  outputType: 'text',
                  status: 'idle',
                  config: { prompt: '测试提示词' },
                },
              },
            ],
            edges: [],
          },
          warnings: [],
          diff: null,
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('创建一个测试工作流')
    await agent.clickGenerate()

    // Wait for the API call
    await page.waitForTimeout(1000)

    expect(generateCalled).toBe(true)
  })

  test('generate failure shows error message', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Mock API failure
    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'LLM 服务不可用' }),
      })
    })

    await agent.setPrompt('测试失败场景')
    await agent.clickGenerate()

    // Wait for error processing
    await page.waitForTimeout(2000)

    // Error message should be displayed
    expect(await agent.hasError()).toBe(true)
    const errorText = await agent.getErrorText()
    expect(errorText.length).toBeGreaterThan(0)
  })

  // --- View Preview ---

  test('successful generation shows preview section', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    // Mock successful API response
    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'preview-wf',
            name: '预览工作流',
            nodes: [
              {
                id: 'textInput-1',
                type: 'studio',
                position: { x: 110, y: 150 },
                data: {
                  label: '主题输入',
                  description: '输入创作主题与要求',
                  kind: 'textInput',
                  outputType: 'text',
                  status: 'idle',
                  config: { prompt: '预览测试' },
                },
              },
            ],
            edges: [],
          },
          warnings: [],
          diff: '新增节点: 主题输入',
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('生成预览测试')
    await agent.clickGenerate()

    // Wait for preview to appear
    await page.waitForTimeout(1500)

    expect(await agent.hasPreview()).toBe(true)
    await expect(agent.applyButton).toBeVisible()
    await expect(agent.cancelButton).toBeVisible()
  })

  test('preview section shows diff information', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'diff-wf',
            name: '差异预览',
            nodes: [],
            edges: [],
          },
          warnings: [],
          diff: '删除 2 个节点, 新增 1 个节点',
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('查看差异预览')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    // Preview section should contain the diff text
    const previewText = await agent.previewSection.textContent()
    expect(previewText).toContain('删除 2 个节点')
  })

  test('preview shows warnings when present', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'warn-wf',
            name: '带警告的工作流',
            nodes: [],
            edges: [],
          },
          warnings: ['节点缺少输入类型', '连线格式不标准'],
          diff: null,
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('查看警告信息')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    // Preview should show warnings
    const previewText = await agent.previewSection.textContent()
    expect(previewText).toContain('节点缺少输入类型')
    expect(previewText).toContain('连线格式不标准')
  })

  test('preview shows destructive warning when applicable', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'destructive-wf',
            name: '破坏性操作',
            nodes: [],
            edges: [],
          },
          warnings: [],
          diff: null,
          patch: { operations: [] },
          destructive: true,
        }),
      })
    })

    await agent.setPrompt('测试破坏性操作')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    const previewText = await agent.previewSection.textContent()
    expect(previewText).toContain('此操作将删除节点或连线')
  })

  // --- Apply Modification ---

  test('clicking apply triggers patch application', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    let applyCalled = false
    let appliedPatch: unknown = null

    // Mock generate-preview
    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: null,
          warnings: [],
          diff: '修改提示词',
          patch: { operations: [{ op: 'replace', path: '/nodes/0/data/config/prompt', value: '新提示词' }] },
          destructive: false,
        }),
      })
    })

    // Mock apply-patch
    await page.route('**/api/agent/apply-patch', (route) => {
      applyCalled = true
      appliedPatch = route.request().postDataJSON()

      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schemaVersion: '1.0',
          id: 'prompt-to-video',
          name: '提示词到短视频',
          nodes: [
            {
              id: 'textInput-1',
              type: 'studio',
              position: { x: 110, y: 150 },
              data: {
                label: '主题输入',
                description: '输入创作主题与要求',
                kind: 'textInput',
                outputType: 'text',
                status: 'idle',
                config: { prompt: '新提示词' },
              },
            },
          ],
          edges: [],
        }),
      })
    })

    // Generate a preview first
    await agent.setPrompt('应用修改测试')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    // Now click apply
    await agent.applyPreview()
    await page.waitForTimeout(1000)

    expect(applyCalled).toBe(true)
    expect(appliedPatch).not.toBeNull()

    // Preview should be dismissed after apply
    expect(await agent.hasPreview()).toBe(false)
  })

  test('clicking cancel dismisses the preview', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    let applyCalled = false
    await page.route('**/api/agent/apply-patch', () => {
      applyCalled = true
    })

    // Mock generate
    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: { schemaVersion: '1.0', id: 'cancel-wf', name: '取消测试', nodes: [], edges: [] },
          warnings: [],
          diff: null,
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('取消测试')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    expect(await agent.hasPreview()).toBe(true)

    // Click cancel
    await agent.cancelPreview()
    await page.waitForTimeout(500)

    // Preview should be hidden
    expect(await agent.hasPreview()).toBe(false)
    // Apply should NOT have been called
    expect(applyCalled).toBe(false)
  })

  test('apply with new workflow spec replaces current workflow', async ({ page }) => {
    const agent = new AgentComposerPage(page)
    const canvas = new CanvasPage(page)
    await agent.waitForReady()

    const initialNodeCount = await canvas.getNodeCount()

    // Mock generate returning a new spec (not a patch)
    await page.route('**/api/agent/generate-preview', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          spec: {
            schemaVersion: '1.0',
            id: 'new-workflow',
            name: '全新工作流',
            nodes: [
              {
                id: 'textInput-1',
                type: 'studio',
                position: { x: 110, y: 150 },
                data: {
                  label: '主题输入',
                  description: '输入创作主题与要求',
                  kind: 'textInput',
                  outputType: 'text',
                  status: 'idle',
                  config: { prompt: '新工作流' },
                },
              },
              {
                id: 'output-1',
                type: 'studio',
                position: { x: 400, y: 150 },
                data: {
                  label: '成片输出',
                  description: '预览与下载最终结果',
                  kind: 'output',
                  inputType: 'video',
                  status: 'idle',
                  config: { filename: 'output.mp4' },
                },
              },
            ],
            edges: [
              { id: 'edge-new', source: 'textInput-1', target: 'output-1', type: 'smoothstep', animated: false },
            ],
          },
          warnings: [],
          diff: null,
          patch: null,
          destructive: false,
        }),
      })
    })

    await agent.setPrompt('替换为新工作流')
    await agent.clickGenerate()
    await page.waitForTimeout(1500)

    expect(await agent.hasPreview()).toBe(true)

    // Apply the new workflow
    await agent.applyPreview()
    await page.waitForTimeout(500)

    // The canvas should now show 2 nodes (replacing the original 6)
    const newNodeCount = await canvas.getNodeCount()
    expect(newNodeCount).toBe(2)
  })
})
