import { ArrowDown, ArrowUp, Plus, Warning } from '@phosphor-icons/react'

import type { PortInfo } from '../types'

interface PortEditorProps {
  inputs: PortInfo[]
  outputs: PortInfo[]
}

function PortRow({ port, direction }: { port: PortInfo; direction: 'input' | 'output' }) {
  const Icon = direction === 'input' ? ArrowDown : ArrowUp
  const iconColor = direction === 'input' ? '#6ee7b7' : '#93c5fd'

  return (
    <div className="port-row">
      <Icon size={13} color={iconColor} weight="bold" />
      <span className="port-row-label">{port.label || port.id}</span>
      <span className={`port-type-badge port-type-badge--${port.type}`}>
        {port.type}
      </span>
      {port.required && (
        <span title="必填"><Warning size={11} color="#fbbf24" weight="fill" /></span>
      )}
      <span className="port-cardinality">
        {port.cardinality === 'many' ? '0..*' : '1'}
      </span>
    </div>
  )
}

function EmptyPorts({ label }: { label: string }) {
  return (
    <div className="port-empty">
      <span>{label}</span>
    </div>
  )
}

export function PortEditor({ inputs, outputs }: PortEditorProps) {
  return (
    <div className="port-editor">
      <div className="port-section">
        <div className="port-section-header">
          <span>输入端口 ({inputs.length})</span>
        </div>
        {inputs.length === 0 ? (
          <EmptyPorts label="无输入端口" />
        ) : (
          inputs.map((port) => (
            <PortRow key={port.id} port={port} direction="input" />
          ))
        )}
      </div>

      <div className="port-section">
        <div className="port-section-header">
          <span>输出端口 ({outputs.length})</span>
        </div>
        {outputs.length === 0 ? (
          <EmptyPorts label="无输出端口" />
        ) : (
          outputs.map((port) => (
            <PortRow key={port.id} port={port} direction="output" />
          ))
        )}
      </div>

      <button className="port-add-btn" disabled title="即将推出">
        <Plus size={12} /> 添加端口 (即将推出)
      </button>
    </div>
  )
}
