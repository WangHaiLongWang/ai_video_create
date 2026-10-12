import type { NodeKind } from '../types'
// HARD-101：数据单一事实来源为 schemas/base-node-manifest.json（repo 根）。
// 本文件只保留类型定义与从共享 JSON 构建的 NODE_CATALOG，禁止再手写端口表。
import manifestDocument from '../../../schemas/base-node-manifest.json'

// ---------------------------------------------------------------------------
// Port types
// ---------------------------------------------------------------------------
export type PortType = 'text' | 'scene' | 'image' | 'video' | 'audio' | 'asset' | 'any'
export type Cardinality = 'one' | 'many'

export interface PortDefinition {
  id: string           // stable handle ID, e.g. "image", "scenes", "scene"
  type: PortType       // base type
  required: boolean    // only meaningful for inputs
  cardinality: Cardinality
  label?: string       // human-readable, defaults to id
}

export interface NodeManifest {
  kind: string             // matches NodeKind
  version: string          // semver
  category: string         // "input" | "transform" | "video" | "output"
  label: string            // display name
  description?: string
  ports: {
    inputs: PortDefinition[]
    outputs: PortDefinition[]
  }
  configSchema?: Record<string, unknown>  // JSON Schema for node config
  execution?: {
    mapOver?: string       // port ID to map over (e.g. "image" for per-scene expansion)
    aggregate?: string     // port ID to aggregate into
  }
}

// ---------------------------------------------------------------------------
// Catalog — built from the shared JSON (single source of truth)
// ---------------------------------------------------------------------------
export const NODE_MANIFEST_DOCUMENT = manifestDocument

function buildCatalog(): Record<NodeKind, NodeManifest> {
  const catalog = {} as Record<NodeKind, NodeManifest>
  for (const entry of manifestDocument.nodeKinds) {
    catalog[entry.kind as NodeKind] = entry as unknown as NodeManifest
  }
  return catalog
}

export const NODE_CATALOG: Record<NodeKind, NodeManifest> = buildCatalog()
