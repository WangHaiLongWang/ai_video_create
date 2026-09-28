import { expect, test, type Page, type Route } from '@playwright/test'

const STORAGE_KEY = 'ai-video-create.workflow.v1'

const SEEDREAM_MODULE = {
  id: 'builtin.seedream.text-to-image',
  version: '1.0.0',
  status: 'published',
  expectedVersion: 4,
  baseKind: 'textToImage',
  category: 'Image',
  label: 'Seedream 5 Image',
  description: 'Generate image variants with Seedream without calling a paid provider in E2E.',
  icon: 'image-square',
  providerPolicy: {
    capability: 'image',
    allowed: ['doubao'],
    default: 'doubao',
    locked: true,
  },
  configSchema: {
    type: 'object',
    properties: {
      image_model: { type: 'string', title: 'Model / Endpoint ID' },
      size: { type: 'string', title: 'Image Size', default: '1280x720' },
      negative_prompt: { type: 'string', title: 'Negative Prompt', format: 'textarea' },
      seed: { type: 'integer', title: 'Seed', minimum: -1, default: -1 },
      watermark: { type: 'boolean', title: 'Watermark', default: false },
      variantCount: { type: 'integer', title: 'Variants', minimum: 1, maximum: 4, default: 1 },
    },
    required: ['image_model'],
  },
  defaultConfig: {
    provider: 'doubao',
    image_model: 'doubao-seedream-5-0-pro-260628',
    size: '1280x720',
    seed: -1,
    watermark: false,
    variantCount: 1,
    mapOver: true,
  },
  ports: {
    inputs: [{ id: 'scene', type: 'scene', required: true, cardinality: 'one', label: 'Scene' }],
    outputs: [{ id: 'image', type: 'image', required: false, cardinality: 'one', label: 'Image' }],
  },
  execution: { mapOver: 'scene' },
  metadata: { builtin: true, provider: 'volcengine' },
} as const

async function mockModuleCatalog(page: Page) {
  await page.route('**/api/modules**', async (route: Route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (request.method() === 'GET' && url.pathname === '/api/modules') {
      const status = url.searchParams.get('status')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(status === 'draft' ? [] : [SEEDREAM_MODULE]),
      })
      return
    }

    if (request.method() === 'GET' && url.pathname.includes('/api/modules/builtin.seedream.text-to-image')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SEEDREAM_MODULE) })
      return
    }

    await route.fallback()
  })
}

async function resetWorkflowOnce(page: Page) {
  await page.addInitScript((key) => {
    if (!sessionStorage.getItem('modules-e2e-initialized')) {
      localStorage.removeItem(key)
      sessionStorage.setItem('modules-e2e-initialized', 'true')
    }
  }, STORAGE_KEY)
}

async function dragSeedreamToCanvas(page: Page) {
  const card = page.locator('.module-card', { hasText: SEEDREAM_MODULE.label })
  await expect(card).toBeVisible()
  const flow = page.locator('main.canvas-shell .react-flow')
  await expect(flow).toBeVisible()

  // Dispatch a real HTML5 drag sequence with one shared DataTransfer object.
  // locator.dragTo relies on pointer hit-testing and the floating Agent panel can
  // legitimately overlap the canvas, while the browser DnD contract is event based.
  const transfer = await page.evaluateHandle(() => new DataTransfer())
  await card.dispatchEvent('dragstart', { dataTransfer: transfer })
  const box = await flow.boundingBox()
  if (!box) throw new Error('React Flow canvas has no bounding box')
  const eventInit = {
    dataTransfer: transfer,
    clientX: box.x + box.width * 0.7,
    clientY: box.y + box.height * 0.25,
  }
  await flow.dispatchEvent('dragenter', eventInit)
  await flow.dispatchEvent('dragover', eventInit)
  await flow.dispatchEvent('drop', eventInit)
  await card.dispatchEvent('dragend', { dataTransfer: transfer })
  await transfer.dispose()
  await expect(page.locator('.react-flow__node', { hasText: SEEDREAM_MODULE.label })).toHaveCount(1)
}

test.describe('Module workflow vertical acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await resetWorkflowOnce(page)
    await mockModuleCatalog(page)
    await page.goto('/')
    await expect(page.locator('main.canvas-shell .react-flow__node').first()).toBeVisible()
  })

  test('published Seedream module appears in the palette and drops onto the canvas', async ({ page }) => {
    const card = page.locator('.module-card', { hasText: SEEDREAM_MODULE.label })
    await expect(card).toContainText('Published')
    await expect(card).toContainText('v1.0.0')
    await expect(card).toContainText('Scene')
    await expect(card).toContainText('Image')

    const before = await page.locator('.react-flow__node').count()
    await dragSeedreamToCanvas(page)
    await expect(page.locator('.react-flow__node')).toHaveCount(before + 1)

    const seedreamNode = page.locator('.react-flow__node', { hasText: SEEDREAM_MODULE.label })
    await expect(seedreamNode.locator('[data-handleid="scene"]')).toHaveAttribute('data-nodeid', /.+/)
    await expect(seedreamNode.locator('[data-handleid="image"]')).toHaveAttribute('data-nodeid', /.+/)

    const stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{}'), STORAGE_KEY)
    const node = stored.nodes.find((item: { data?: { moduleId?: string } }) => item.data?.moduleId === SEEDREAM_MODULE.id)
    expect(node.data.moduleVersion).toBe(SEEDREAM_MODULE.version)
    expect(node.data.ports).toEqual(SEEDREAM_MODULE.ports)
    expect(node.data.config.provider).toBe('doubao')
    expect(node.data.config.image_model).toBe('doubao-seedream-5-0-pro-260628')
    expect(node.data.configOverrides).toEqual({})
  })

  test('schema-driven override persists through localStorage reload without mutating module defaults', async ({ page }) => {
    await dragSeedreamToCanvas(page)
    await page.locator('.react-flow__node', { hasText: SEEDREAM_MODULE.label }).click()

    const properties = page.locator('aside.properties')
    await expect(properties).toContainText('Seedream 5 Image v1.0.0')
    await expect(properties.locator('select').filter({ has: page.locator('option[value="doubao"]') })).toBeDisabled()

    const variants = properties.locator('label', { hasText: 'Variants' }).locator('input[type="number"]')
    await expect(variants).toHaveValue('1')
    await variants.fill('3')
    await expect.poll(async () => page.evaluate((key) => {
      const workflow = JSON.parse(localStorage.getItem(key) ?? '{}')
      return workflow.nodes.find((item: { data?: { moduleId?: string } }) => item.data?.moduleId === 'builtin.seedream.text-to-image')?.data?.configOverrides?.variantCount
    }, STORAGE_KEY)).toBe(3)

    await page.reload()
    await expect(page.locator('.react-flow__node', { hasText: SEEDREAM_MODULE.label })).toHaveCount(1)
    await page.locator('.react-flow__node', { hasText: SEEDREAM_MODULE.label }).click()
    await expect(page.locator('aside.properties label', { hasText: 'Variants' }).locator('input[type="number"]')).toHaveValue('3')

    const stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{}'), STORAGE_KEY)
    const node = stored.nodes.find((item: { data?: { moduleId?: string } }) => item.data?.moduleId === SEEDREAM_MODULE.id)
    expect(node.data.configOverrides).toEqual({ variantCount: 3 })
    expect(node.data.config.variantCount).toBe(1)
    expect(node.data.moduleId).toBe(SEEDREAM_MODULE.id)
    expect(node.data.moduleVersion).toBe(SEEDREAM_MODULE.version)
  })
})

test('Module Designer creates, saves and publishes through the versioned API contract', async ({ page }) => {
  await resetWorkflowOnce(page)
  const requests: Array<{ method: string; path: string; body: unknown }> = []
  let savedDefinition: Record<string, unknown> | null = null

  await page.route('**/api/modules**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const body = request.postDataJSON?.() ?? null

    if (request.method() === 'GET' && url.pathname === '/api/modules') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      return
    }

    if (request.method() === 'POST' && url.pathname === '/api/modules') {
      savedDefinition = body as Record<string, unknown>
      requests.push({ method: request.method(), path: url.pathname, body })
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...savedDefinition, expectedVersion: 1 }),
      })
      return
    }

    if (request.method() === 'POST' && url.pathname.endsWith('/publish')) {
      requests.push({ method: request.method(), path: url.pathname, body })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...savedDefinition, status: 'published', expectedVersion: 2 }),
      })
      return
    }

    await route.fallback()
  })

  await page.goto('/')
  await page.locator('.module-palette-create-btn').click()
  const designer = page.locator('.md-panel')
  await expect(designer).toBeVisible()
  await designer.locator('label', { hasText: 'Label' }).locator('input').fill('My Seedream Module')
  await designer.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => requests.filter((item) => item.path === '/api/modules').length).toBe(1)

  await designer.getByRole('button', { name: 'Publish', exact: true }).click()
  await expect.poll(() => requests.filter((item) => item.path.endsWith('/publish')).length).toBe(1)
  await expect(designer.locator('.md-status-badge')).toHaveText('Published')

  expect(requests[0].body).toMatchObject({
    id: 'image.my-seedream-module',
    label: 'My Seedream Module',
    status: 'draft',
    baseKind: 'textToImage',
  })
  expect(requests[1]).toMatchObject({
    method: 'POST',
    path: '/api/modules/image.my-seedream-module/publish',
    body: { version: '0.1.0', expectedVersion: 1 },
  })
})
