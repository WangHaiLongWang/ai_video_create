import { useState } from 'react'
import { Robot, Sparkle } from '@phosphor-icons/react'
import { useStudioStore } from '../store'
import { createPromptToVideoWorkflow } from '../workflow'

export function AgentComposer() {
  const [prompt, setPrompt] = useState('创建一个 5 镜头的未来城市短视频流程')
  const [open, setOpen] = useState(true)
  const setWorkflow = useStudioStore((state) => state.setWorkflow)

  const generate = () => {
    const count = Number(prompt.match(/(\d+)\s*镜头/)?.[1] ?? 5)
    const workflow = createPromptToVideoWorkflow(prompt)
    const storyboard = workflow.nodes.find((node) => node.data.kind === 'storyboard')
    if (storyboard) storyboard.data.config.scenes = Math.min(Math.max(count, 1), 20)
    setWorkflow(workflow)
  }

  if (!open) return <button className="agent-fab" onClick={() => setOpen(true)} aria-label="打开 Agent"><Robot size={21} /></button>
  return (
    <section className="agent-composer">
      <div className="agent-title"><Robot size={18} weight="duotone" /><strong>Workflow Agent</strong><button onClick={() => setOpen(false)}>收起</button></div>
      <div className="agent-input">
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} aria-label="描述想要创建的工作流" />
        <button onClick={generate}><Sparkle size={17} weight="fill" />生成流程</button>
      </div>
      <p>本地规则模式。接入 LLM 后将生成结构化 WorkflowSpec，并在应用前展示差异。</p>
    </section>
  )
}
