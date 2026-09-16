import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  ChatCenteredText,
  FilmStrip,
  ImageSquare,
  MagicWand,
  TextT,
  VideoCamera,
} from '@phosphor-icons/react'
import { NODE_CATALOG } from './schemas/node-manifest'
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
  const manifest = NODE_CATALOG[data.kind]
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

  return (
    <article className={`studio-node status-${data.status} ${selected ? 'is-selected' : ''}`}>
      {/* Input handles on the left */}
      {inputs.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="target"
          position={Position.Left}
          className={`node-handle handle-${port.type} ${port.required ? 'handle-required' : ''}`}
          style={{ top: `${30 + (i + 1) * (100 / (inputs.length + 1))}%` }}
        />
      ))}

      <header>
        <span className="node-icon"><Icon size={17} weight="duotone" /></span>
        <div>
          <strong>{data.label}</strong>
          <small>{data.description}</small>
        </div>
      </header>

      <div className="node-meta">
        {inputs.map(p => <span key={p.id} className="port-label port-input">{p.label ?? p.id}</span>)}
        {outputs.map(p => <span key={p.id} className="port-label port-output">{p.label ?? p.id}</span>)}
      </div>

      {data.status === 'running' && <div className="node-progress" aria-label="执行中" />}

      {/* Output handles on the right */}
      {outputs.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type="source"
          position={Position.Right}
          className={`node-handle handle-${port.type}`}
          style={{ top: `${30 + (i + 1) * (100 / (outputs.length + 1))}%` }}
        />
      ))}
    </article>
  )
}
