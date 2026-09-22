import { useState, useEffect, useMemo } from 'react'
import { Package, Plus } from '@phosphor-icons/react'
import type { ModuleDefinition } from '../schemas/module-definition'
import { BUILTIN_MODULES } from '../schemas/module-definition'
import { fetchModules } from '../api/modules'
import { ModuleCard } from './ModuleCard'
import { useModuleDesignerStore } from '../store/moduleDesignerSlice'

export function ModulePalette() {
  const [modules, setModules] = useState<ModuleDefinition[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { openDesigner } = useModuleDesignerStore()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchModules('published')
      .then((remote) => {
        if (!cancelled) {
          // Merge built-in modules with remote, deduplicating by id
          const byId = new Map<string, ModuleDefinition>()
          for (const mod of BUILTIN_MODULES) byId.set(mod.id, mod)
          for (const mod of remote) byId.set(mod.id, mod)
          setModules(Array.from(byId.values()))
        }
      })
      .catch(() => {
        // Fall back to built-in modules when API is unavailable
        if (!cancelled) {
          setModules(BUILTIN_MODULES)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const handleModuleClick = (mod: ModuleDefinition) => {
    openDesigner(mod.id, mod)
  }

  const handleCreateModule = () => {
    openDesigner()
  }

  const grouped = useMemo(() => {
    const groups = new Map<string, ModuleDefinition[]>()
    for (const mod of modules) {
      const list = groups.get(mod.category) ?? []
      list.push(mod)
      groups.set(mod.category, list)
    }
    return groups
  }, [modules])

  const onDragStart = (event: React.DragEvent, mod: ModuleDefinition) => {
    event.dataTransfer.setData('application/reactflow-module', JSON.stringify({
      moduleId: mod.id,
      moduleVersion: mod.version,
      baseKind: mod.baseKind,
      label: mod.label,
      description: mod.description ?? '',
      configOverrides: {},
    }))
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="module-palette">
      <div className="module-palette-header">
        <Package size={14} />
        <span>模块库</span>
        <button
          className="module-palette-create-btn"
          onClick={handleCreateModule}
          title="Create new module"
        >
          <Plus size={14} />
        </button>
      </div>
      {loading && <p className="module-palette-hint">加载中...</p>}
      {error && <p className="module-palette-hint module-palette-error">{error}</p>}
      {!loading && modules.length === 0 && (
        <p className="module-palette-hint">暂无可用模块</p>
      )}
      {Array.from(grouped.entries()).map(([category, mods]) => (
        <div key={category} className="module-palette-group">
          <div className="module-palette-group-title">{category}</div>
          <div className="module-palette-list">
            {mods.map((mod) => (
              <ModuleCard
                key={mod.id}
                module={mod}
                onDragStart={onDragStart}
                onClick={handleModuleClick}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
