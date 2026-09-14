import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  ChatCenteredText,
  FilmStrip,
  ImageSquare,
  MagicWand,
  TextT,
  VideoCamera,
} from '@phosphor-icons/react'
import type { StudioNode } from './types'

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
  return (
    <article className={`studio-node status-${data.status} ${selected ? 'is-selected' : ''}`}>
      {data.inputType && <Handle type="target" position={Position.Left} className="node-handle" />}
      <header>
        <span className="node-icon"><Icon size={17} weight="duotone" /></span>
        <div>
          <strong>{data.label}</strong>
          <small>{data.description}</small>
        </div>
      </header>
      <div className="node-meta">
        <span>{data.inputType ?? '开始'}</span>
        <span>{data.outputType ?? '结束'}</span>
      </div>
      {data.status === 'running' && <div className="node-progress" aria-label="执行中" />}
      {data.outputType && <Handle type="source" position={Position.Right} className="node-handle" />}
    </article>
  )
}
