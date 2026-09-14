import { describe, expect, it } from 'vitest'
import { createPromptToVideoWorkflow, validateConnection } from './workflow'

describe('workflow contract', () => {
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

