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
import { useStudioStore } from './store'

/** Two port types are compatible when identical or either is 'any'. */
function typesCompatible(a: string, b: string): boolean {
  return a === b || a === 'any' || b === 'any'
}

const icons = {
  textInput: TextT,
  storyboard: ChatCenteredText,
  textToImage: ImageSquare,
  imageToVideo: VideoCamera,
  videoConcat: FilmStrip,
  output: MagicWand,
}

export function StudioNodeView({ id, data, selected }: NodeProps<StudioNode>) {
  const Icon = icons[data.kind]
  const connectingFrom = useStudioStore(s => s.connectingFrom)
  const errorTarget = useStudioStore(s => s.errorTarget)

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

  // Determine if a target (input) handle is compatible with the active source port
  const isCompatible = (port: PortInfo): boolean => {
    if (!connectingFrom) return true // no active drag, all normal
    if (connectingFrom.nodeId === id) return false // self-loop
    return typesCompatible(connectingFrom.portType, port.type)
  }

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

  // Determine active source handle for highlighting
  const isSourceNode = connectingFrom?.nodeId === id
  const isConnecting = connectingFrom !== null

  // Error indicator for this node
  const isErrorNode = errorTarget?.nodeId === id

  return (
    <article
      className={[
        'studio-node',
        `status-${data.status}`,
        selected ? 'is-selected' : '',
        isConnecting ? 'is-connecting' : '',
      ].filter(Boolean).join(' ')}
    >
      {/* Input handles — left side */}
      {inputs.map((port, i) => {
        const compatible = isCompatible(port)
        const isErrorHandle = isErrorNode && errorTarget?.handleId === port.id
        return (
          <Handle
            key={port.id}
            id={port.id}
            type="target"
            position={Position.Left}
            className={[
              'node-handle',
              `handle-${port.type}`,
              port.required ? 'handle-required' : '',
              isConnecting && compatible ? 'handle-compatible' : '',
              isConnecting && !compatible ? 'handle-incompatible' : '',
              isErrorHandle ? 'handle-error' : '',
            ].filter(Boolean).join(' ')}
            style={{ top: handleTop(i, inputs.length) }}
            aria-label={`Input: ${port.label ?? port.id} (${port.type})${!compatible ? ' - incompatible' : ''}`}
          />
        )
      })}

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
      {outputs.map((port, i) => {
        const isActiveSource = isSourceNode && connectingFrom?.handleId === port.id
        return (
          <Handle
            key={port.id}
            id={port.id}
            type="source"
            position={Position.Right}
            className={[
              'node-handle',
              `handle-${port.type}`,
              isActiveSource ? 'handle-active-source' : '',
            ].filter(Boolean).join(' ')}
            style={{ top: handleTop(i, outputs.length) }}
            aria-label={`Output: ${port.label ?? port.id} (${port.type})`}
          />
        )
      })}
    </article>
  )
}
