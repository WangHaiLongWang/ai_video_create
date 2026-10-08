import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { AgentComposerPage } from './pages'

/**
 * MOD-R3-004 — Agent Modify real-browser integration against the real Mock FastAPI.
 *
 * Acceptance (docs/plans/active/MODULAR-NODE-SEEDREAM-PLAN.md):
 *   "Modify Preview 真实浏览器联调，展示 module/version/config diff | 修改不重建，destructive 需确认"
 *
 * Zero `page.route`: every assertion is driven by the live Mock backend
 * (`AI_VIDEO_*_PROVIDER=mock`) started by playwright.config.ts webServer.
 *
 * Deterministic MockProvider modify behaviour (backend/app/providers/mock_provider.py):
 * prompts containing "Modify this existing WorkflowIntent" echo the existing
 * topology and tweak exactly one config value (`mockTweak: "modified"`), so a
 * modify round-trip is a config diff — not a rebuild.
 *
 * Destructive path: MockProvider never drops nodes on its own. The real modify
 * pipeline does, however, drop the video `output` sink of image-only workflows
 * (`workflow_intent_parser._normalize_image_only_intent`). Seeding a valid
 * image-only graph that still has an `output` node therefore yields a real
 * `destructive: true` patch — no route mock, no monkeypatch.
 */

const STORAGE_KEY = 'ai-video-create.workflow.v1'
const SEEDREAM_ID = 'builtin.seedream.text-to-image'

function uniqueSuffix(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

type SpecNode = {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

type SpecEdge = {
  id: string
  source: string
  sourceHandle: string
  target: string
  targetHandle: string
  type: string
  data: { mode: string; label: string }
}

type SpecWorkflow = {
  schemaVersion: string
  id: string
  name: string
  description: string
  nodes: SpecNode[]
  edges: SpecEdge[]
  viewport: { x: number; y: number; zoom: number }
}

function makeNode(
  id: string,
  kind: string,
  label: string,
  extra: Partial<SpecNode['data']> = {},
): SpecNode {
  return {
    id,
    type: 'studio',
    position: { x: 100, y: 150 },
    data: {
      label,
      description: '',
      kind,
      status: 'idle',
      config: {},
      ...extra,
    },
  }
}

function makeEdge(
  id: string,
  source: string,
  sourceHandle: string,
  target: string,
  targetHandle: string,
): SpecEdge {
  return {
    id,
    source,
    sourceHandle,
    target,
    targetHandle,
    type: 'smoothstep',
    data: { mode: 'direct', label: '' },
  }
}

function makeWorkflow(
  id: string,
  name: string,
  nodes: SpecNode[],
  edges: SpecEdge[],
): SpecWorkflow {
  return {
    schemaVersion: '2.0',
    id,
    name,
    description: '',
    nodes,
    edges,
    viewport: { x: 0, y: 0, zoom: 1 },
  }
}

/** textInput → storyboard → textToImage — a valid chain (storyboard.prompt is wired). */
function threeNodeChain(suffix: string): SpecWorkflow {
  const n0 = `chain-in-${suffix}`
  const n1 = `chain-story-${suffix}`
  const n2 = `chain-img-${suffix}`
  return makeWorkflow(
    `e2e-modify-chain-${suffix}`,
    `E2E Modify Chain ${suffix}`,
    [
      makeNode(n0, 'textInput', '主题输入', {
        outputType: 'text',
        config: { prompt: '雨夜送信人' },
      }),
      makeNode(n1, 'storyboard', '分镜生成', {
        inputType: 'text',
        outputType: 'list<scene>',
        config: { scenes: 3, provider: 'Mock' },
      }),
      makeNode(n2, 'textToImage', '文生图', {
        inputType: 'list<scene>',
        outputType: 'list<image>',
        config: { ratio: '16:9' },
      }),
    ],
    [
      makeEdge(`chain-e0-${suffix}`, n0, 'text', n1, 'prompt'),
      makeEdge(`chain-e1-${suffix}`, n1, 'scenes', n2, 'scene'),
    ],
  )
}

/**
 * textInput → storyboard → Seedream module node.
 * The module node carries real registry ports so POST /api/workflows validates.
 */
async function seedreamChain(
  request: APIRequestContext,
  suffix: string,
): Promise<SpecWorkflow> {
  const modRes = await request.get(`/api/modules/${SEEDREAM_ID}`)
  expect(modRes.status(), 'builtin Seedream module must be resolvable').toBe(200)
  const mod = await modRes.json()
  expect(mod.version).toBeTruthy()

  const n0 = `mod-in-${suffix}`
  const n1 = `mod-story-${suffix}`
  const n2 = `mod-img-${suffix}`
  return makeWorkflow(
    `e2e-modify-module-${suffix}`,
    `E2E Modify Module ${suffix}`,
    [
      makeNode(n0, 'textInput', '主题输入', {
        outputType: 'text',
        config: { prompt: '模块化修改' },
      }),
      makeNode(n1, 'storyboard', '分镜生成', {
        inputType: 'text',
        outputType: 'list<scene>',
        config: { scenes: 2, provider: 'Mock' },
      }),
      makeNode(n2, 'textToImage', mod.label, {
        inputType: mod.ports?.inputs?.[0]?.type ?? 'scene',
        outputType: mod.ports?.outputs?.[0]?.type ?? 'image',
        config: {
          provider: 'doubao',
          image_model: 'doubao-seedream-5-0-pro-260628',
          ratio: '16:9',
        },
        moduleId: SEEDREAM_ID,
        moduleVersion: mod.version,
        configOverrides: {},
        ports: mod.ports,
      }),
    ],
    [
      makeEdge(`mod-e0-${suffix}`, n0, 'text', n1, 'prompt'),
      makeEdge(`mod-e1-${suffix}`, n1, 'scenes', n2, 'scene'),
    ],
  )
}

/**
 * Image-only workflow that still has an `output` node.
 *
 * The output port is typed `image` (and non-required) so the graph passes the
 * live REQUIRED_PORT / type gates. On modify, `_normalize_image_only_intent`
 * drops that sink — a real destructive patch (remove node + its edge).
 */
function imageOnlyWithOutput(suffix: string): SpecWorkflow {
  const n0 = `img-in-${suffix}`
  const n1 = `img-story-${suffix}`
  const n2 = `img-t2i-${suffix}`
  const n3 = `img-out-${suffix}`
  return makeWorkflow(
    `e2e-modify-destructive-${suffix}`,
    `E2E Modify Destructive ${suffix}`,
    [
      makeNode(n0, 'textInput', '主题输入', {
        outputType: 'text',
        config: { prompt: '静帧海报' },
      }),
      makeNode(n1, 'storyboard', '分镜生成', {
        inputType: 'text',
        outputType: 'list<scene>',
        config: { scenes: 2, provider: 'Mock' },
      }),
      makeNode(n2, 'textToImage', '文生图', {
        inputType: 'list<scene>',
        outputType: 'list<image>',
        config: { ratio: '16:9' },
      }),
      makeNode(n3, 'output', '成片输出', {
        inputType: 'video',
        config: {},
        ports: {
          inputs: [
            { id: 'video', type: 'image', required: false, cardinality: 'one', label: 'video' },
          ],
          outputs: [],
        },
      }),
    ],
    [
      makeEdge(`img-e0-${suffix}`, n0, 'text', n1, 'prompt'),
      makeEdge(`img-e1-${suffix}`, n1, 'scenes', n2, 'scene'),
      makeEdge(`img-e2-${suffix}`, n2, 'image', n3, 'video'),
    ],
  )
}

/** POST the spec to the real API and load the same spec into the canvas store. */
async function seedAndLoad(page: Page, request: APIRequestContext, spec: SpecWorkflow) {
  const created = await request.post('/api/workflows', { data: spec })
  expect(
    created.status(),
    `seed ${spec.id} failed: ${await created.text()}`,
  ).toBe(201)
  const summary = await created.json()

  await page.addInitScript(
    ({ key, payload }) => {
      localStorage.setItem(key, payload)
    },
    { key: STORAGE_KEY, payload: JSON.stringify(spec) },
  )
  await page.goto('/')
  await expect(page.locator('main.canvas-shell .react-flow__node').first()).toBeVisible()
  await expect(page.locator('section.agent-composer')).toBeVisible()
  return summary
}

async function fetchWorkflow(request: APIRequestContext, id: string) {
  const res = await request.get(`/api/workflows/${id}`)
  expect(res.status(), `GET /api/workflows/${id}`).toBe(200)
  return res.json()
}

function nodeIds(wf: { spec: { nodes: Array<{ id: string }> } }): string[] {
  return wf.spec.nodes.map((n) => n.id)
}

function edgeIds(wf: { spec: { edges: Array<{ id: string }> } }): string[] {
  return wf.spec.edges.map((e) => e.id)
}

/** Drive modify-mode submit and wait for the real modify-preview-v2 response. */
async function submitModifyAndGetPreview(
  page: Page,
  agent: AgentComposerPage,
  instruction: string,
) {
  const modifyPost = page.waitForResponse(
    (r) =>
      r.url().includes('/api/agent/modify-preview-v2') &&
      r.request().method() === 'POST',
  )
  await agent.enterModifyMode()
  await agent.setModifyInstruction(instruction)
  await agent.submitModify()
  const res = await modifyPost
  expect(res.status(), `modify-preview-v2 failed: ${await res.text()}`).toBe(200)
  return res.json()
}

test.describe('Agent Modify real-browser integration (MOD-R3-004)', () => {
  test('modify preview shows incremental diff + module/version/config diffs (not a rebuild)', async ({
    page,
    request,
  }) => {
    test.setTimeout(45_000)
    const suffix = uniqueSuffix()
    const spec = await seedreamChain(request, suffix)
    await seedAndLoad(page, request, spec)

    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    const preview = await submitModifyAndGetPreview(page, agent, '调整分镜与图片配置')

    // Real contract: the four incremental fields are present on modify.
    expect(preview.patch, 'patch should be present for modify').toBeTruthy()
    expect(preview.diff).toBeTruthy()
    expect(preview.destructive).toBe(false)
    expect(Array.isArray(preview.module_diffs)).toBe(true)

    // Patch references the ORIGINAL node ids — 修改不重建 at the contract level.
    const originalIds = spec.nodes.map((n) => n.id)
    const compiledIds = (preview.compiled_workflow?.nodes ?? []).map(
      (n: { id: string }) => n.id,
    )
    expect(compiledIds).toEqual(originalIds)
    for (const update of preview.patch.update_nodes as Array<{ id: string }>) {
      expect(originalIds, `patch.update_nodes id ${update.id}`).toContain(update.id)
    }
    // Topology untouched: no adds/removes in this non-destructive modify.
    expect(preview.patch.add_nodes).toEqual([])
    expect(preview.patch.remove_nodes).toEqual([])
    expect(preview.patch.add_edges).toEqual([])
    expect(preview.patch.remove_edges).toEqual([])
    expect(preview.patch.update_nodes.length).toBeGreaterThan(0)

    // --- UI: incremental diff is the PRIMARY view ---
    await expect(agent.patchSection).toBeVisible()
    await expect(agent.patchSection).toContainText('变更内容（增量 Diff）')
    // Full "编译后工作流" listing must NOT dominate when a patch exists.
    await expect(agent.compiledWorkflowSection).toHaveCount(0)

    const patchItems = await agent.getPatchItemTexts()
    expect(
      patchItems.some((t) => t.includes('修改节点')),
      `patch rows should show 修改节点, got: ${JSON.stringify(patchItems)}`,
    ).toBe(true)

    // Diff text from the real response (~ 更新 N 个节点: …).
    await expect(agent.diffSection).toBeVisible()
    const diffText = await agent.getDiffText()
    expect(diffText).toContain('更新')
    for (const id of originalIds) {
      expect(diffText, `diff should mention node id ${id}`).toContain(id)
    }

    // --- UI: module / version / config diff visible ---
    // Live mock+compiler round-trip classifies the Seedream node as 配置变更
    // (reconfigured) because compile materialises configOverrides from config.
    await expect(agent.moduleDiffsSection).toBeVisible()
    await expect(agent.moduleDiffsSection).toContainText('模块变更')
    await expect(agent.moduleDiffsSection).toContainText('配置变更')
    await expect(agent.moduleDiffsSection).toContainText(SEEDREAM_ID)

    const moduleDiffs = preview.module_diffs as Array<Record<string, unknown>>
    expect(moduleDiffs.length).toBeGreaterThan(0)
    const seedreamDiff = moduleDiffs.find((d) => d.moduleId === SEEDREAM_ID)
    expect(seedreamDiff, `module_diffs should include ${SEEDREAM_ID}`).toBeTruthy()
    expect(seedreamDiff?.type).toBe('reconfigured')
    expect(seedreamDiff?.nodeId).toBe(spec.nodes[2].id)

    // Intent preview carries moduleId@moduleVersion chips.
    const chips = await agent.getIntentModuleChips()
    expect(
      chips.some((t) => t.includes(SEEDREAM_ID)),
      `intent chips should include ${SEEDREAM_ID}, got: ${JSON.stringify(chips)}`,
    ).toBe(true)
    expect(
      chips.some((t) => t.includes('1.0.0')),
      `intent chips should include the module version, got: ${JSON.stringify(chips)}`,
    ).toBe(true)

    // Non-destructive: no confirm banner / alertdialog.
    await expect(agent.destructiveBanner).toHaveCount(0)
    await expect(agent.destructiveConfirm).toHaveCount(0)
  })

  test('修改不重建: apply preserves untouched node/edge ids on the server', async ({
    page,
    request,
  }) => {
    test.setTimeout(45_000)
    const suffix = uniqueSuffix()
    const spec = threeNodeChain(suffix)
    const summary = await seedAndLoad(page, request, spec)
    const originalNodeIds = spec.nodes.map((n) => n.id)
    const originalEdgeIds = spec.edges.map((e) => e.id)

    const before = await fetchWorkflow(request, spec.id)
    expect(before.version).toBe(summary.version)
    expect(nodeIds(before)).toEqual(originalNodeIds)

    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    const preview = await submitModifyAndGetPreview(page, agent, '把分镜改成 3 场并调整风格')
    expect(preview.destructive).toBe(false)
    expect(preview.can_apply).toBe(true)
    expect(preview.patch).toBeTruthy()

    // Apply through the real POST /api/agent/apply-v2.
    const applyPost = page.waitForResponse(
      (r) => r.url().includes('/api/agent/apply-v2') && r.request().method() === 'POST',
    )
    await agent.applyPreviewAndWait()
    const applyRes = await applyPost
    expect(applyRes.status()).toBe(200)
    const applied = await applyRes.json()
    expect(applied.success).toBe(true)
    expect(applied.workflow_id).toBe(spec.id)

    // Core acceptance: the server workflow keeps the ORIGINAL node/edge ids.
    const after = await fetchWorkflow(request, spec.id)
    expect(
      nodeIds(after),
      'untouched node ids must survive modify+apply (修改不重建)',
    ).toEqual(originalNodeIds)
    expect(edgeIds(after)).toEqual(originalEdgeIds)
    expect(after.version).toBeGreaterThan(before.version)

    // The change is a config tweak on the storyboard node, not a rebuild.
    const storyboard = after.spec.nodes.find((n: { id: string }) => n.id === originalNodeIds[1])
    expect(storyboard, 'storyboard node should still exist').toBeTruthy()
    const storyboardData = (storyboard?.data ?? {}) as { config?: Record<string, unknown> }
    expect(
      storyboardData.config?.mockTweak,
      'mock modify lands mockTweak on the storyboard config',
    ).toBe('modified')

    // Canvas still shows the same three nodes after the local patch apply.
    await expect(page.locator('main.canvas-shell .react-flow__node')).toHaveCount(3)
    await expect(agent.successBanner).toContainText('已应用')
  })

  test('destructive modify requires confirmation; cancel is a no-op; confirm deletes', async ({
    page,
    request,
  }) => {
    test.setTimeout(45_000)
    const suffix = uniqueSuffix()
    const spec = imageOnlyWithOutput(suffix)
    const summary = await seedAndLoad(page, request, spec)
    const outputNodeId = spec.nodes[3].id
    const outputEdgeId = spec.edges[2].id
    const originalNodeIds = spec.nodes.map((n) => n.id)

    const before = await fetchWorkflow(request, spec.id)
    expect(nodeIds(before)).toEqual(originalNodeIds)

    const agent = new AgentComposerPage(page)
    await agent.waitForReady()

    const preview = await submitModifyAndGetPreview(page, agent, '删除输出节点')

    // Real response marks the patch destructive (output sink dropped).
    expect(preview.destructive, 'image-only output sink must produce a destructive patch').toBe(true)
    expect(preview.can_apply).toBe(true)
    const removeNodes = (preview.patch?.remove_nodes ?? []) as string[]
    const removeEdges = (preview.patch?.remove_edges ?? []) as string[]
    expect(removeNodes).toContain(outputNodeId)
    expect(removeEdges).toContain(outputEdgeId)

    // Destructive banner + deletion list, no auto-apply.
    await expect(agent.destructiveBanner).toBeVisible()
    await expect(agent.destructiveBanner).toContainText(
      '此操作包含删除（破坏性变更），应用前需二次确认',
    )
    await expect(agent.destructiveBanner).toContainText(outputNodeId)
    await expect(agent.patchSection).toBeVisible()
    await expect(agent.patchSection).toContainText('删除节点')

    // Apply click opens the confirm alertdialog instead of applying.
    await agent.openDestructiveConfirm()
    await expect(agent.destructiveConfirm).toBeVisible()
    await expect(agent.destructiveConfirm).toContainText('确认删除以下内容并应用？')
    const confirmList = await agent.getDestructiveConfirmListTexts()
    expect(
      confirmList.some((t) => t.includes(outputNodeId)),
      `confirm list should mention ${outputNodeId}, got: ${JSON.stringify(confirmList)}`,
    ).toBe(true)

    // Cancel: nothing reaches the server.
    await agent.cancelDestructiveConfirm()
    const afterCancel = await fetchWorkflow(request, spec.id)
    expect(afterCancel.version, 'cancel must not bump the server version').toBe(before.version)
    expect(nodeIds(afterCancel)).toEqual(originalNodeIds)
    expect(edgeIds(afterCancel)).toEqual(spec.edges.map((e) => e.id))

    // Re-open confirm and apply the deletion.
    await agent.openDestructiveConfirm()
    const applyPost = page.waitForResponse(
      (r) => r.url().includes('/api/agent/apply-v2') && r.request().method() === 'POST',
    )
    await agent.confirmDestructiveApply()
    const applyRes = await applyPost
    expect(applyRes.status()).toBe(200)
    const applied = await applyRes.json()
    expect(applied.success).toBe(true)

    await agent.successBanner.waitFor({ state: 'visible' })

    const afterApply = await fetchWorkflow(request, spec.id)
    expect(afterApply.version).toBeGreaterThan(before.version)
    const remaining = nodeIds(afterApply)
    expect(remaining, 'output node must be gone after confirm').not.toContain(outputNodeId)
    expect(remaining.sort()).toEqual([...originalNodeIds.slice(0, 3)].sort())
    expect(edgeIds(afterApply)).not.toContain(outputEdgeId)
    // Untouched nodes keep their ids (修改不重建 even on a destructive patch).
    for (const id of originalNodeIds.slice(0, 3)) {
      expect(remaining).toContain(id)
    }
  })
})
