import { describe, expect, it } from 'vitest'
import { createModuleNode, createPromptToVideoWorkflow, validateConnection } from './workflow'
import { BUILTIN_MODULES } from './schemas/module-definition'

describe('workflow contract', () => {
  it('creates a module node from the exact module contract', () => {
    const definition = BUILTIN_MODULES[0]
    const node = createModuleNode(definition, 20, 30, 'module-1')

    expect(node.data.moduleId).toBe(definition.id)
    expect(node.data.moduleVersion).toBe(definition.version)
    expect(node.data.ports?.inputs.map((port) => port.id)).toEqual(definition.ports.inputs.map((port) => port.id))
    expect(node.data.ports?.outputs.map((port) => port.id)).toEqual(definition.ports.outputs.map((port) => port.id))
    expect(node.data.config).toMatchObject(definition.defaultConfig ?? {})
    expect(node.data.configOverrides).toEqual({})
  })

  it('creates a typed prompt-to-video pipeline', () => {
    const workflow = createPromptToVideoWorkflow('测试主题')
    expect(workflow.nodes).toHaveLength(6)
    expect(workflow.edges).toHaveLength(5)
    expect(workflow.nodes[0].data.config.prompt).toBe('测试主题')
  })

  it('only connects compatible port types', () => {
    const workflow = createPromptToVideoWorkflow()
    expect(validateConnection(workflow.nodes[0], workflow.nodes[1])).toBe(true)
    expect(validateConnection(workflow.nodes[0], workflow.nodes[3])).toBe(false)
  })
})
