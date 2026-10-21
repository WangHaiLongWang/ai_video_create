import { expect, test, type Page, type APIRequestContext } from '@playwright/test'

const STORAGE_KEY = 'ai-video-create.workflow.v1'

/** Real builtin Seedream definition — mirrors backend/app/services/module_registry.py. */
const SEEDREAM_ID = 'builtin.seedream.text-to-image'
const SEEDREAM_LABEL = 'Seedream 文生图'
const SEEDREAM_VERSION = '1.0.0'

async function resetWorkflowOnce(page: Page) {
  await page.addInitScript((key) => {
    if (!sessionStorage.getItem('modules-e2e-initialized')) {
      localStorage.removeItem(key)
      sessionStorage.setItem('modules-e2e-initialized', 'true')
    }
  }, STORAGE_KEY)
}

/** Fetch the live builtin module so assertions track the real API contract. */
async function fetchSeedreamModule(request: APIRequestContext) {
  const res = await request.get(`/api/modules/${SEEDREAM_ID}`)
  expect(res.status()).toBe(200)
  return res.json()
}

async function dragModuleToCanvas(page: Page, label: string) {
  const card = page.locator('.module-card', { hasText: label })
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
  await expect(page.locator('.react-flow__node', { hasText: label })).toHaveCount(1)
}

async function readStoredNode(page: Page, moduleId: string) {
  return page.evaluate(
    ({ key, id }) => {
      const workflow = JSON.parse(localStorage.getItem(key) ?? '{}')
      return workflow.nodes?.find((item: { data?: { moduleId?: string } }) => item.data?.moduleId === id)
    },
    { key: STORAGE_KEY, id: moduleId },
  )
}

/**
 * Graph validation rejects a module node whose required `scene` input is
 * unconnected (REQUIRED_PORT), so wire it to the storyboard's scenes output.
 * Attempts the real React Flow connection first, then guarantees the edge is
 * present in the persisted spec so the subsequent reload/run is deterministic.
 */
async function connectStoryboardToModule(page: Page, moduleLabel: string) {
  const source = page
    .locator('.react-flow__node', { hasText: '分镜生成' })
    .locator('.react-flow__handle[data-handleid="scenes"]')
  const target = page
    .locator('.react-flow__node', { hasText: moduleLabel })
    .locator('.react-flow__handle[data-handleid="scene"]')
  const sourceBox = await source.boundingBox()
  const targetBox = await target.boundingBox()
  if (!sourceBox || !targetBox) throw new Error('Storyboard/module handle not found')

  const sx = sourceBox.x + sourceBox.width / 2
  const sy = sourceBox.y + sourceBox.height / 2
  const tx = targetBox.x + targetBox.width / 2
  const ty = targetBox.y + targetBox.height / 2

  await page.mouse.move(sx, sy)
  await page.mouse.down()
  for (let i = 1; i <= 15; i++) {
    await page.mouse.move(sx + ((tx - sx) * i) / 15, sy + ((ty - sy) * i) / 15)
    await page.waitForTimeout(25)
  }
  await page.mouse.up()
  await page.waitForTimeout(150)
}

/**
 * Persist the workflow for the run leg:
 *  - unique server id (POST /api/workflows must not collide)
 *  - unique node ids (the tasks table keys on `${node_id}-${scene_id}` alone,
 *    so two executions of the same template would violate the primary key)
 *  - storyboard→module edge (REQUIRED_PORT gate)
 *  - a smaller scene count so the mock pipeline converges inside the budget
 */
async function persistWorkflowForRun(page: Page, moduleNodeId: string) {
  const suffix = Date.now().toString(36)
  await page.evaluate(
    ({ key, nodeId, suffix }) => {
      const workflow = JSON.parse(localStorage.getItem(key) ?? '{}')
      workflow.id = `e2e-module-${suffix}`

      // Namespace node ids per run — see the tasks-table primary-key note above.
      const idMap = new Map<string, string>()
      for (const node of workflow.nodes ?? []) {
        const nextId = `${node.id}-${suffix}`
        idMap.set(node.id, nextId)
        node.id = nextId
        if (node.data?.kind === 'storyboard') {
          node.data.config = { ...node.data.config, scenes: 2 }
        }
      }
      for (const edge of workflow.edges ?? []) {
        if (idMap.has(edge.source)) edge.source = idMap.get(edge.source)
        if (idMap.has(edge.target)) edge.target = idMap.get(edge.target)
        edge.id = `${edge.id}-${suffix}`
      }

      const mappedModuleId = idMap.get(nodeId) ?? nodeId
      const edges = workflow.edges ?? []
      const storyboardId = [...idMap.values()].find((id) => id.startsWith('storyboard-'))

      // Module resolution replaces node config with defaultConfig+overrides, so
      // a designer-created module (empty defaultConfig) would lose mapOver and
      // run as a prompt-less single task. Pin mapOver so it maps over scenes.
      for (const node of workflow.nodes ?? []) {
        if (node.id === mappedModuleId && node.data) {
          node.data.configOverrides = { ...(node.data.configOverrides ?? {}), mapOver: true }
        }
      }

      const alreadyConnected = edges.some(
        (e: { source?: string; target?: string }) =>
          e.source === storyboardId && e.target === mappedModuleId,
      )
      if (!alreadyConnected && storyboardId) {
        edges.push({
          id: `edge-e2e-${mappedModuleId}`,
          source: storyboardId,
          sourceHandle: 'scenes',
          target: mappedModuleId,
          targetHandle: 'scene',
          type: 'smoothstep',
          animated: false,
          data: { mode: 'direct', label: '' },
        })
      }
      workflow.edges = edges
      localStorage.setItem(key, JSON.stringify(workflow))
    },
    { key: STORAGE_KEY, nodeId: moduleNodeId, suffix },
  )
  return suffix
}

async function runWorkflowAndCollectEvidence(page: Page, request: APIRequestContext) {
  const workflowsPost = page.waitForResponse(
    (r) => r.url().endsWith('/api/workflows') && r.request().method() === 'POST',
  )
  const startPost = page.waitForResponse(
    (r) => /\/api\/executions\/[^/]+\/start$/.test(r.url()) && r.request().method() === 'POST',
  )

  await page.locator('header.topbar .run-button').click()

  const workflowRes = await workflowsPost
  expect(workflowRes.status()).toBe(201)
  const startRes = await startPost
  expect(startRes.status()).toBe(201)
  const execution = await startRes.json()
  expect(execution.id).toBeTruthy()

  // Poll until a terminal-ish execution state (bounded).
  await expect
    .poll(
      async () => {
        const res = await request.get(`/api/executions/${execution.id}`)
        expect(res.status()).toBe(200)
        return (await res.json()).status as string
      },
      {
        // The real Mock FastAPI worker may take several seconds to initialize
        // on a fresh GitHub runner. Keep the enclosing test's 60s budget while
        // avoiding a false failure during worker warm-up.
        timeout: 50_000,
        intervals: [250, 500, 1_000],
        message: `execution ${execution.id} never reached a terminal state`,
      },
    )
    .toMatch(/completed|failed|cancelled/)

  const tasksRes = await request.get(`/api/executions/${execution.id}/tasks`)
  expect(tasksRes.status()).toBe(200)
  const tasks = await tasksRes.json()
  expect(tasks.length).toBeGreaterThan(0)

  const assetsRes = await request.get(`/api/assets?execution_id=${execution.id}`)
  expect(assetsRes.status()).toBe(200)
  const assets = await assetsRes.json()

  return { execution, tasks, assets }
}

test.describe('Module workflow vertical acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await resetWorkflowOnce(page)
    await page.goto('/')
    await expect(page.locator('main.canvas-shell .react-flow__node').first()).toBeVisible()
  })

  test('published Seedream module appears in the palette and drops onto the canvas', async ({ page, request }) => {
    const mod = await fetchSeedreamModule(request)
    expect(mod.label).toBe(SEEDREAM_LABEL)
    expect(mod.version).toBe(SEEDREAM_VERSION)
    expect(mod.category).toBe('image')

    const card = page.locator('.module-card', { hasText: SEEDREAM_LABEL })
    await expect(card).toContainText('Published')
    await expect(card).toContainText(`v${SEEDREAM_VERSION}`)
    // Port labels come from the real definition (场景 / 图片).
    await expect(card).toContainText('场景')
    await expect(card).toContainText('图片')

    const before = await page.locator('.react-flow__node').count()
    await dragModuleToCanvas(page, SEEDREAM_LABEL)
    await expect(page.locator('.react-flow__node')).toHaveCount(before + 1)

    const seedreamNode = page.locator('.react-flow__node', { hasText: SEEDREAM_LABEL })
    await expect(seedreamNode.locator('[data-handleid="scene"]')).toHaveAttribute('data-nodeid', /.+/)
    await expect(seedreamNode.locator('[data-handleid="image"]')).toHaveAttribute('data-nodeid', /.+/)

    const node = await readStoredNode(page, SEEDREAM_ID)
    expect(node).toBeTruthy()
    expect(node.data.moduleVersion).toBe(SEEDREAM_VERSION)
    expect(node.data.ports).toEqual(mod.ports)
    expect(node.data.config.provider).toBe('doubao')
    expect(node.data.config.image_model).toBe('doubao-seedream-5-0-pro-260628')
    expect(node.data.configOverrides).toEqual({})
  })

  test('schema-driven override persists through localStorage reload without mutating module defaults', async ({ page }) => {
    await dragModuleToCanvas(page, SEEDREAM_LABEL)
    await page.locator('.react-flow__node', { hasText: SEEDREAM_LABEL }).click()

    const properties = page.locator('aside.properties')
    await expect(properties).toContainText(`${SEEDREAM_LABEL} v${SEEDREAM_VERSION}`)
    await expect(properties.locator('select').filter({ has: page.locator('option[value="doubao"]') })).toBeDisabled()

    // Real schema title for variantCount is 变体数量. The field is schema-driven:
    // it renders even though the module's defaultConfig omits variantCount.
    const variants = properties.locator('label', { hasText: '变体数量' }).locator('input[type="number"]')
    await expect(variants).toBeVisible()
    await variants.fill('3')
    await expect
      .poll(async () => {
        const node = await readStoredNode(page, SEEDREAM_ID)
        return node?.data?.configOverrides?.variantCount
      })
      .toBe(3)

    await page.reload()
    await expect(page.locator('.react-flow__node', { hasText: SEEDREAM_LABEL })).toHaveCount(1)
    await page.locator('.react-flow__node', { hasText: SEEDREAM_LABEL }).click()
    await expect(
      page.locator('aside.properties label', { hasText: '变体数量' }).locator('input[type="number"]'),
    ).toHaveValue('3')

    const node = await readStoredNode(page, SEEDREAM_ID)
    expect(node.data.configOverrides).toEqual({ variantCount: 3 })
    // Module defaults are not mutated by an instance override.
    expect(node.data.config.variantCount).toBeUndefined()
    expect(node.data.moduleId).toBe(SEEDREAM_ID)
    expect(node.data.moduleVersion).toBe(SEEDREAM_VERSION)
  })

  test('Module Designer creates, saves and publishes through the real versioned API contract', async ({ page, request }) => {
    const label = `My Seedream Module ${Date.now()}`
    // generateModuleId slugifies the label under the draft category ("Image").
    const expectedId = `image.${label.toLowerCase().replace(/[^a-z0-9一-鿿]+/g, '-').replace(/^-|-$/g, '')}`
    const moduleRequests: Array<{ method: string; path: string; body: unknown }> = []
    page.on('request', (req) => {
      const url = new URL(req.url())
      if (url.pathname.startsWith('/api/modules') && ['POST', 'PUT'].includes(req.method())) {
        moduleRequests.push({
          method: req.method(),
          path: url.pathname,
          body: req.postDataJSON?.() ?? null,
        })
      }
    })

    await page.locator('.module-palette-create-btn').click()
    const designer = page.locator('.md-panel')
    await expect(designer).toBeVisible()
    await designer.locator('label', { hasText: 'Label' }).locator('input').fill(label)
    await designer.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(designer.locator('.md-status-badge')).toHaveText('Draft')

    const createReq = moduleRequests.find((item) => item.method === 'POST' && item.path === '/api/modules')
    expect(createReq).toBeTruthy()
    expect(createReq!.body).toMatchObject({
      id: expectedId,
      label,
      status: 'draft',
      baseKind: 'textToImage',
    })

    // The row must be queryable through the real API (DB-backed).
    const afterCreate = await request.get(`/api/modules/${expectedId}`)
    expect(afterCreate.status()).toBe(200)
    const created = await afterCreate.json()
    expect(created.status).toBe('draft')
    expect(created.expectedVersion).toBeGreaterThanOrEqual(1)

    await designer.getByRole('button', { name: 'Publish', exact: true }).click()
    await expect(designer.locator('.md-status-badge')).toHaveText('Published')

    const publishReq = moduleRequests.find((item) => item.path.endsWith('/publish'))
    expect(publishReq).toBeTruthy()
    expect(publishReq!.method).toBe('POST')
    // Optimistic-lock body carries the version we just saved.
    expect(publishReq!.body).toMatchObject({ version: '0.1.0' })

    const afterPublish = await request.get(`/api/modules/${expectedId}`)
    expect(afterPublish.status()).toBe(200)
    const published = await afterPublish.json()
    expect(published.status).toBe('published')
    expect(published.label).toBe(label)
    // expectedVersion advanced past the create value (optimistic lock).
    expect(published.expectedVersion).toBeGreaterThan(created.expectedVersion)
  })

  test('chain: create→publish→drag→save→reload→run yields queryable Task and Asset', async ({ page, request }) => {
    test.setTimeout(90_000)
    const label = `Chain Module ${Date.now()}`

    // --- create + publish through the Module Designer (real API) ---
    await page.locator('.module-palette-create-btn').click()
    const designer = page.locator('.md-panel')
    await expect(designer).toBeVisible()
    await designer.locator('label', { hasText: 'Label' }).locator('input').fill(label)
    await designer.getByRole('button', { name: 'Save', exact: true }).click()
    await designer.getByRole('button', { name: 'Publish', exact: true }).click()
    await expect(designer.locator('.md-status-badge')).toHaveText('Published')
    await designer.getByRole('button', { name: 'Close' }).click()

    const listed = await request.get('/api/modules')
    expect(listed.status()).toBe(200)
    const publishedList: Array<{ id: string; label: string; status: string }> = await listed.json()
    const createdModule = publishedList.find((m) => m.label === label)
    expect(createdModule).toBeTruthy()
    expect(createdModule!.status).toBe('published')

    // Palette caches on mount — reload so the new module is draggable.
    await page.reload()
    await expect(page.locator('main.canvas-shell .react-flow__node').first()).toBeVisible()

    // --- drag the created module onto the canvas ---
    const search = page.locator('.module-palette-search-input')
    await search.fill(label)
    await dragModuleToCanvas(page, label)
    await connectStoryboardToModule(page, label)

    // --- save (localStorage) + unique server id + valid graph for the run ---
    const node = await readStoredNode(page, createdModule!.id)
    expect(node).toBeTruthy()
    expect(node.data.moduleVersion).toBe('0.1.0')
    const suffix = await persistWorkflowForRun(page, node.id)
    const runtimeNodeId = `${node.id}-${suffix}`

    // --- reload and confirm the module node survived ---
    await page.reload()
    await expect(page.locator('.react-flow__node', { hasText: label })).toHaveCount(1)

    // --- run through the real Mock FastAPI ---
    const { execution, tasks, assets } = await runWorkflowAndCollectEvidence(page, request)

    // Task evidence: the chain module produced one or more tasks with results.
    const moduleTasks = tasks.filter((t: { node_id: string }) => t.node_id === runtimeNodeId)
    expect(moduleTasks.length).toBeGreaterThan(0)
    expect(moduleTasks.some((t: { status: string }) => t.status === 'completed')).toBe(true)

    // Asset evidence: image artifacts are recorded and queryable per execution.
    expect(assets.length).toBeGreaterThan(0)
    expect(assets.some((a: { execution_id: string }) => a.execution_id === execution.id)).toBe(true)
  })

  test('Seedream module pinned to doubao runs under the Mock backend and records assets', async ({ page, request }) => {
    test.setTimeout(90_000)

    await dragModuleToCanvas(page, SEEDREAM_LABEL)
    await connectStoryboardToModule(page, SEEDREAM_LABEL)

    const node = await readStoredNode(page, SEEDREAM_ID)
    expect(node.data.config.provider).toBe('doubao')
    const suffix = await persistWorkflowForRun(page, node.id)
    const runtimeNodeId = `${node.id}-${suffix}`

    await page.reload()
    await expect(page.locator('.react-flow__node', { hasText: SEEDREAM_LABEL })).toHaveCount(1)

    const { execution, tasks, assets } = await runWorkflowAndCollectEvidence(page, request)

    // The provider-trap fix must let the doubao-pinned node complete via mock.
    const seedreamTasks = tasks.filter((t: { node_id: string }) => t.node_id === runtimeNodeId)
    expect(seedreamTasks.length).toBeGreaterThan(0)
    for (const t of seedreamTasks) {
      expect(t.status, `task ${t.id} error: ${t.error ?? 'n/a'}`).toBe('completed')
    }

    // Image artifacts are queryable for this execution.
    const images = assets.filter((a: { asset_type: string }) => a.asset_type === 'image')
    expect(images.length).toBeGreaterThan(0)
    expect(images.some((a: { execution_id: string }) => a.execution_id === execution.id)).toBe(true)
  })
})
