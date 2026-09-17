import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  ChatCenteredText,
  FilmStrip,
  ImageSquare,
  MagicWand,
  TextT,
  VideoCamera,
} from '@phosphor-icons/react'
import type { StudioNode, PortInfo } from './types'

const icons = {
  textInput: TextT,
  storyboard: ChatCenteredText,
  textToImage: ImageSquare,
  imageToVideo: VideoCamera,
  videoConcat: FilmStrip,
  output: MagicWand,
}

export function StudioNodeView({ data, selected }: NodeProps<StudioNode>) {
  const Icon = icons[data.kind]
  const inputs: PortInfo[] = data.ports?.inputs ?? (
    data.inputType
      ? [{ id: 'in', type: data.inputType, required: true, cardinality: 'one' }]
      : []
  )
  const outputs: PortInfo[] = data.ports?.outputs ?? (
    data.outputType
      ? [{ id: 'out', type: data.outputType, required: false, cardinality: 'one' }]
      : []
  )

  // Distribute handles evenly along left/right edges using percentage-based top.
  // React Flow positions Handle DOM elements at these percentages of the node height.
  // Input handles: left side, 25%..75% range
  // Output handles: right side, 25%..75% range
  function handleTop(index: number, total: number): string {
    if (total === 1) return '50%'
    const start = 30
    const end = 70
    const step = (end - start) / (total - 1)
    return `${start + index * step}%`
  }

  return (
    <article className={`studio-node status-${data.status} ${selected ? 'is-selected' : ''}`}>
      {/* Input handles — left side */}
      {inputs.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="target"
          position={Position.Left}
          className={`node-handle handle-${port.type} ${port.required ? 'handle-required' : ''}`}
          style={{ top: handleTop(i, inputs.length) }}
        />
      ))}

      {/* Port labels — left side, positioned absolutely outside overflow */}
      {inputs.map((port, i) => (
        <span
          key={`label-${port.id}`}
          className="port-label port-label-left"
          style={{ top: handleTop(i, inputs.length) }}
        >
          {port.label ?? port.id}
        </span>
      ))}

      <header>
        <span className="node-icon"><Icon size={17} weight="duotone" /></span>
        <div>
          <strong>{data.label}</strong>
          <small>{data.description}</small>
        </div>
      </header>

      <div className="node-config-summary">
        {data.kind}
      </div>

      {data.status === 'running' && <div className="node-progress" aria-label="执行中" />}

      {/* Port labels — right side */}
      {outputs.map((port, i) => (
        <span
          key={`label-${port.id}`}
          className="port-label port-label-right"
          style={{ top: handleTop(i, outputs.length) }}
        >
          {port.label ?? port.id}
        </span>
      ))}

      {/* Output handles — right side */}
      {outputs.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="source"
          position={Position.Right}
          className={`node-handle handle-${port.type}`}
          style={{ top: handleTop(i, outputs.length) }}
        />
      ))}
    </article>
  )
}
