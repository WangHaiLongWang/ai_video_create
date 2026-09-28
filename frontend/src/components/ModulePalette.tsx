import { useState, useEffect, useMemo } from 'react'
import { Package, Plus, MagnifyingGlass, User } from '@phosphor-icons/react'
import type { ModuleDefinition, ModuleCategory } from '../schemas/module-definition'
import { BUILTIN_MODULES } from '../schemas/module-definition'
import { fetchModules, cloneModule } from '../api/modules'
import { ModuleCard } from './ModuleCard'
import { useModuleDesignerStore } from '../store/moduleDesignerSlice'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const ALL_CATEGORIES: ModuleCategory[] = ['Input', 'LLM', 'Image', 'Video', 'Transform', 'Output']

const CATEGORY_LABELS: Record<string, string> = {
  Input: 'Input',
  LLM: 'LLM',
  Image: 'Image',
  Video: 'Video',
  Transform: 'Transform',
  Output: 'Output',
  'My Modules': 'My Modules',
  All: 'All',
}

export function ModulePalette() {
  const [modules, setModules] = useState<ModuleDefinition[]>([])
  const [userModules, setUserModules] = useState<ModuleDefinition[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('All')
  const [searchQuery, setSearchQuery] = useState('')
  const { openDesigner } = useModuleDesignerStore()

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    // Fetch published modules (builtins + remote)
    setError(null)
    Promise.all([fetchModules('published'), fetchModules('draft')])
      .then(([published, drafts]) => {
        if (!cancelled) {
          // Merge built-in modules with remote published, deduplicating by id
          const byId = new Map<string, ModuleDefinition>()
          for (const mod of BUILTIN_MODULES) byId.set(`${mod.id}@${mod.version}`, mod)
          for (const mod of published) byId.set(`${mod.id}@${mod.version}`, mod)
          setModules(Array.from(byId.values()))

          // User modules = drafts + published that aren't builtins
          const builtinIds = new Set(BUILTIN_MODULES.map((m) => m.id))
          const userByDraftId = new Map<string, ModuleDefinition>()
          for (const mod of drafts) {
            if (!builtinIds.has(mod.id)) {
              userByDraftId.set(mod.id, mod)
            }
          }
          // Also include non-builtin published modules
          for (const mod of published) {
            if (!builtinIds.has(mod.id)) {
              userByDraftId.set(mod.id, mod)
            }
          }
          setUserModules(Array.from(userByDraftId.values()))
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setModules(BUILTIN_MODULES)
          setError(err instanceof Error ? err.message : 'Failed to load modules')
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

  const handleClone = async (mod: ModuleDefinition) => {
    try {
      await cloneModule(mod.id)
      // Reload modules after clone
      const [published, drafts] = await Promise.all([
        fetchModules('published').catch(() => []),
        fetchModules('draft').catch(() => []),
      ])
      const byId = new Map<string, ModuleDefinition>()
      for (const m of BUILTIN_MODULES) byId.set(`${m.id}@${m.version}`, m)
      for (const m of published) byId.set(`${m.id}@${m.version}`, m)
      setModules(Array.from(byId.values()))

      const builtinIds = new Set(BUILTIN_MODULES.map((m) => m.id))
      const userByDraftId = new Map<string, ModuleDefinition>()
      for (const m of drafts) {
        if (!builtinIds.has(m.id)) userByDraftId.set(m.id, m)
      }
      for (const m of published) {
        if (!builtinIds.has(m.id)) userByDraftId.set(m.id, m)
      }
      setUserModules(Array.from(userByDraftId.values()))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clone module')
    }
  }

  // ---------------------------------------------------------------------------
  // Search filtering
  // ---------------------------------------------------------------------------
  const searchFilter = (mod: ModuleDefinition): boolean => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      mod.label.toLowerCase().includes(q) ||
      mod.description?.toLowerCase().includes(q) ||
      mod.category.toLowerCase().includes(q) ||
      mod.id.toLowerCase().includes(q) ||
      mod.providerPolicy?.capability?.toLowerCase().includes(q)
    )
  }

  // ---------------------------------------------------------------------------
  // Grouped modules by category
  // ---------------------------------------------------------------------------
  const allFilteredModules = useMemo(() => {
    const unique = new Map<string, ModuleDefinition>()
    for (const mod of [...modules, ...userModules]) {
      unique.set(`${mod.id}@${mod.version}`, mod)
    }
    return Array.from(unique.values()).filter(searchFilter)
  }, [modules, userModules, searchQuery])

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const mod of allFilteredModules) {
      counts[mod.category] = (counts[mod.category] || 0) + 1
    }
    return counts
  }, [allFilteredModules])

  const myModulesCount = useMemo(() => {
    return userModules.filter(searchFilter).length
  }, [userModules, searchFilter])

  const groupedByCategory = useMemo(() => {
    const groups = new Map<string, ModuleDefinition[]>()
    const filtered = activeCategory === 'My Modules'
      ? userModules.filter(searchFilter)
      : activeCategory === 'All'
        ? allFilteredModules
        : allFilteredModules.filter((m) => m.category.toLowerCase() === activeCategory.toLowerCase())

    for (const mod of filtered) {
      const list = groups.get(mod.category) ?? []
      list.push(mod)
      groups.set(mod.category, list)
    }
    return groups
  }, [allFilteredModules, userModules, activeCategory, searchFilter])

  const onDragStart = (event: React.DragEvent, mod: ModuleDefinition) => {
    event.dataTransfer.setData('application/reactflow-module', JSON.stringify(mod))
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

      {/* Search bar */}
      <div className="module-palette-search">
        <MagnifyingGlass size={12} />
        <input
          type="text"
          placeholder="搜索模块..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="module-palette-search-input"
        />
        {searchQuery && (
          <button
            className="module-palette-search-clear"
            onClick={() => setSearchQuery('')}
            title="Clear search"
          >
            ×
          </button>
        )}
      </div>

      {/* Category tabs */}
      <div className="module-palette-tabs">
        <button
          className={`module-palette-tab ${activeCategory === 'All' ? 'module-palette-tab-active' : ''}`}
          onClick={() => setActiveCategory('All')}
        >
          All
          <span className="module-palette-tab-count">{allFilteredModules.length}</span>
        </button>
        {ALL_CATEGORIES.map((cat) => (
          <button
            key={cat}
            className={`module-palette-tab ${activeCategory === cat ? 'module-palette-tab-active' : ''}`}
            onClick={() => setActiveCategory(cat)}
          >
            {CATEGORY_LABELS[cat] ?? cat}
            {categoryCounts[cat] ? (
              <span className="module-palette-tab-count">{categoryCounts[cat]}</span>
            ) : null}
          </button>
        ))}
        <button
          className={`module-palette-tab module-palette-tab-my ${activeCategory === 'My Modules' ? 'module-palette-tab-active' : ''}`}
          onClick={() => setActiveCategory('My Modules')}
        >
          <User size={10} />
          My Modules
          {myModulesCount > 0 && (
            <span className="module-palette-tab-count">{myModulesCount}</span>
          )}
        </button>
      </div>

      {loading && <p className="module-palette-hint">加载中...</p>}
      {error && <p className="module-palette-hint module-palette-error">{error}</p>}
      {!loading && allFilteredModules.length === 0 && (
        <p className="module-palette-hint">暂无可用模块</p>
      )}

      {/* Module groups */}
      {activeCategory === 'My Modules' ? (
        <div className="module-palette-group">
          <div className="module-palette-group-title">
            <User size={10} /> My Modules
          </div>
          <div className="module-palette-list">
            {userModules.filter(searchFilter).length === 0 ? (
              <p className="module-palette-hint">No user-created modules yet</p>
            ) : (
              userModules.filter(searchFilter).map((mod) => (
                <ModuleCard
                  key={`${mod.id}@${mod.version}`}
                  module={mod}
                  onDragStart={onDragStart}
                  onClick={handleModuleClick}
                  onClone={handleClone}
                />
              ))
            )}
          </div>
        </div>
      ) : (
        Array.from(groupedByCategory.entries()).map(([category, mods]) => (
          <div key={category} className="module-palette-group">
            <div className="module-palette-group-title">{category}</div>
            <div className="module-palette-list">
              {mods.map((mod) => (
                <ModuleCard
                  key={`${mod.id}@${mod.version}`}
                  module={mod}
                  onDragStart={onDragStart}
                  onClick={handleModuleClick}
                  onClone={handleClone}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
