import type { ModuleDefinition } from '../schemas/module-definition'

interface ModuleCardProps {
  module: ModuleDefinition
  onDragStart?: (event: React.DragEvent, mod: ModuleDefinition) => void
  onClick?: (mod: ModuleDefinition) => void
}

export function ModuleCard({ module, onDragStart, onClick }: ModuleCardProps) {
  const inputSummary = module.ports.inputs.map((p) => p.label ?? p.id).join(', ') || '--'
  const outputSummary = module.ports.outputs.map((p) => p.label ?? p.id).join(', ') || '--'

  return (
    <button
      className="module-card"
      draggable
      onDragStart={(e) => onDragStart?.(e, module)}
      onClick={() => onClick?.(module)}
    >
      <div className="module-card-header">
        <span className="module-card-label">{module.label}</span>
        <span className="module-card-version">v{module.version}</span>
      </div>
      {module.description && (
        <p className="module-card-desc">{module.description}</p>
      )}
      <div className="module-card-meta">
        <span className="module-card-category">{module.category}</span>
        {module.providerPolicy.locked && (
          <span className="module-card-lock" title="Provider locked">
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1a3 3 0 0 0-3 3v2H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-1V4a3 3 0 0 0-3-3zm-2 3a2 2 0 1 1 4 0v2H6V4z" />
            </svg>
            {module.providerPolicy.allowed.join(', ')}
          </span>
        )}
      </div>
      <div className="module-card-ports">
        <span className="module-card-port-in">{inputSummary}</span>
        <span className="module-card-arrow">&rarr;</span>
        <span className="module-card-port-out">{outputSummary}</span>
      </div>
    </button>
  )
}
