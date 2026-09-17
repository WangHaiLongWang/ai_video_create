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

  return (
    <div className="studio-node-shell">
      {/* Input handles before the card */}
      {inputs.map(port => (
        <div key={port.id} className="port-row port-row-input">
          <Handle
            id={port.id}
            type="target"
            position={Position.Left}
            className={`node-handle handle-${port.type} ${port.required ? 'handle-required' : ''}`}
          />
          <span className="port-label">{port.label ?? port.id}</span>
        </div>
      ))}

      <article className={`studio-node-card status-${data.status} ${selected ? 'is-selected' : ''}`}>
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
      </article>

      {/* Output handles after the card */}
      {outputs.map(port => (
        <div key={port.id} className="port-row port-row-output">
          <span className="port-label">{port.label ?? port.id}</span>
          <Handle
            id={port.id}
            type="source"
            position={Position.Right}
            className={`node-handle handle-${port.type}`}
          />
        </div>
      ))}
    </div>
  )
}
