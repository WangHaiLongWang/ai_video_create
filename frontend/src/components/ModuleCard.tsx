import type { ModuleDefinition, ModuleStatus } from '../schemas/module-definition'

const STATUS_COLORS: Record<ModuleStatus, string> = {
  draft: '#b8a44e',
  published: '#7dce7d',
  archived: '#737a6e',
}

const STATUS_LABELS: Record<ModuleStatus, string> = {
  draft: 'Draft',
  published: 'Published',
  archived: 'Archived',
}

interface ModuleCardProps {
  module: ModuleDefinition
  onDragStart?: (event: React.DragEvent, mod: ModuleDefinition) => void
  onClick?: (mod: ModuleDefinition) => void
  onClone?: (mod: ModuleDefinition) => void
}

export function ModuleCard({ module, onDragStart, onClick, onClone }: ModuleCardProps) {
  const inputSummary = module.ports.inputs.map((p) => p.label ?? p.id).join(', ') || '--'
  const outputSummary = module.ports.outputs.map((p) => p.label ?? p.id).join(', ') || '--'

  const handleClone = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClone?.(module)
  }

  return (
    <div
      className="module-card"
      role="button"
      tabIndex={0}
      draggable
      onDragStart={(e) => onDragStart?.(e, module)}
      onClick={() => onClick?.(module)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.(module)
        }
      }}
    >
      <div className="module-card-header">
        <span className="module-card-label">{module.label}</span>
        <div className="module-card-badges">
          <span
            className="module-card-status"
            style={{ color: STATUS_COLORS[module.status] }}
            title={`Status: ${STATUS_LABELS[module.status]}`}
          >
            {STATUS_LABELS[module.status]}
          </span>
          <span className="module-card-version">v{module.version}</span>
        </div>
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
      {onClone && !module.metadata?.builtin && (
        <div className="module-card-actions">
          <button
            className="module-card-action-btn"
            onClick={handleClone}
            title="Clone module"
          >
            Clone
          </button>
        </div>
      )}
    </div>
  )
}
