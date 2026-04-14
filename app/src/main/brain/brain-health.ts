import { execFile } from 'child_process'
import { existsSync, readFileSync } from 'fs'
import path from 'path'
import yaml from 'js-yaml'
import type { BrainHealthData, OrphanBreakdown, RelationshipTypeCount } from '../../shared/types'

const DEFAULT_TARGETS = {
  connectivityRate: 85,
  entityCount: 500,
  medianRelationships: 3,
  graphComponents: 1,
  orphanRate: 10,
  staleEntityRate: 15,
  enrichmentVelocity7d: 10,
}

// Python tool output — primary source of truth for graph metrics
interface GraphHealthJson {
  total_entities: number
  entities_with_relationships: number
  orphan_entities: number
  total_relationships: number
  relationship_coverage: number
  avg_relationships_per_entity: number
  density_score: number
  entities_by_type: Record<string, number>
  relationships_by_type: Record<string, number>
  orphans: string[]
  most_connected: Array<[string, number]>
  inferred_edge_count: number
  // New fields (Phase 2 — added to graph_health.py)
  connected_components?: number
  graph_diameter?: number | null
  median_relationships?: number
}

interface OrphanJson {
  total_entities: number
  total_orphans: number
  orphan_rate: number
  orphans_by_type: Record<string, number>
  orphans_by_reason: Record<string, number>
  sample_orphans: Array<{ id: string; type: string; name: string; reason: string }>
}

function getPythonBin(pmosPath: string): string {
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  return existsSync(venvPython) ? venvPython : 'python3'
}

function runPythonTool(pythonBin: string, scriptPath: string, args: string[], pmosPath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(pythonBin, [scriptPath, ...args], {
      timeout: 60000,
      env: { ...process.env, PM_OS_ROOT: pmosPath, PYTHONPATH: path.join(pmosPath, 'common', 'tools') },
      cwd: path.join(pmosPath, 'common', 'tools', 'brain'),
    }, (err, stdout, stderr) => {
      if (err) reject(new Error(`${err.message}${stderr ? ': ' + stderr : ''}`))
      else resolve(stdout)
    })
  })
}

/**
 * Read timestamp-based metrics from registry.yaml.
 * Registry is used ONLY for: stale entity rate, enrichment velocity, last update timestamp.
 * Graph structure metrics come from Python tools.
 */
function readRegistryTimestampMetrics(pmosPath: string): {
  staleEntityRate: number
  enrichmentVelocity7d: number
  lastEntityUpdate: string | null
} {
  const registryPath = path.join(pmosPath, 'user', 'brain', 'registry.yaml')
  if (!existsSync(registryPath)) {
    return { staleEntityRate: 0, enrichmentVelocity7d: 0, lastEntityUpdate: null }
  }

  try {
    const registryContent = readFileSync(registryPath, 'utf-8')
    const registryRaw = yaml.load(registryContent) as Record<string, any>

    // Registry v2 nests entities under an `entities` key; v1 is flat
    const registry: Record<string, any> = registryRaw.entities && typeof registryRaw.entities === 'object'
      ? registryRaw.entities
      : registryRaw

    const entities = Object.values(registry).filter((e: any) => e && typeof e === 'object' && e.$type)
    if (entities.length === 0) {
      return { staleEntityRate: 0, enrichmentVelocity7d: 0, lastEntityUpdate: null }
    }

    const now = Date.now()

    // Stale entity detection based on $updated timestamps
    const STALENESS_THRESHOLDS: Record<string, number> = {
      person: 90, team: 60, squad: 60, project: 30, experiment: 14,
      system: 90, domain: 180, brand: 180, default: 90,
    }
    let staleCount = 0
    for (const entity of entities) {
      const e = entity as any
      if (!e.$updated) { staleCount++; continue }
      const updated = new Date(e.$updated).getTime()
      const daysSince = (now - updated) / (1000 * 60 * 60 * 24)
      const threshold = STALENESS_THRESHOLDS[e.$type] || STALENESS_THRESHOLDS.default
      if (daysSince > threshold) staleCount++
    }

    // Enrichment velocity: entities updated in last 7 days
    const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000
    let recentlyUpdated = 0
    let latestUpdate: string | null = null
    for (const entity of entities) {
      const e = entity as any
      if (!e.$updated) continue
      const updated = new Date(e.$updated).getTime()
      if (updated > sevenDaysAgo) recentlyUpdated++
      if (!latestUpdate || e.$updated > latestUpdate) latestUpdate = e.$updated
    }

    return {
      staleEntityRate: entities.length > 0 ? Math.round((staleCount / entities.length) * 100) : 0,
      enrichmentVelocity7d: recentlyUpdated,
      lastEntityUpdate: latestUpdate,
    }
  } catch {
    return { staleEntityRate: 0, enrichmentVelocity7d: 0, lastEntityUpdate: null }
  }
}

/**
 * Read the last enrichment timestamp from enrichment state files.
 * Checks both enrichment_state.json (orchestrator) and .enrichment-state.json (brain_enrich.py).
 */
function readLastEnrichmentTimestamp(brainPath: string): string | null {
  let latest: string | null = null

  // Check enrichment_state.json (written by orchestrator and brain_enrich.py after Phase 4 fix)
  try {
    const statePath = path.join(brainPath, 'enrichment_state.json')
    if (existsSync(statePath)) {
      const state = JSON.parse(readFileSync(statePath, 'utf-8'))
      if (state.last_run) latest = state.last_run
    }
  } catch { /* ignore */ }

  // Check .enrichment-state.json (written by brain_enrich.py) — use file mtime as proxy
  try {
    const hiddenStatePath = path.join(brainPath, '.enrichment-state.json')
    if (existsSync(hiddenStatePath)) {
      const stat = require('fs').statSync(hiddenStatePath)
      const mtime = stat.mtime.toISOString()
      if (!latest || mtime > latest) latest = mtime
    }
  } catch { /* ignore */ }

  return latest
}

export async function computeBrainHealth(pmosPath: string): Promise<BrainHealthData> {
  const pythonBin = getPythonBin(pmosPath)
  const toolsDir = path.join(pmosPath, 'common', 'tools', 'brain')
  const brainPath = path.join(pmosPath, 'user', 'brain')

  // Load targets from config if available
  const configTargets = { ...DEFAULT_TARGETS }
  try {
    const configPath = path.join(pmosPath, 'user', 'config.yaml')
    if (existsSync(configPath)) {
      const configContent = readFileSync(configPath, 'utf-8')
      const config = yaml.load(configContent) as Record<string, any>
      if (config?.brain?.target_entity_count) configTargets.entityCount = config.brain.target_entity_count
    }
  } catch { /* use defaults */ }

  // Read timestamp-based metrics from registry (fast, synchronous)
  const registryMetrics = readRegistryTimestampMetrics(pmosPath)

  // Read enrichment timestamp from state files
  const lastEnrichment = readLastEnrichmentTimestamp(brainPath) || registryMetrics.lastEntityUpdate

  // Run Python tools — primary source for all graph structure metrics
  let graphHealth: GraphHealthJson | null = null
  let orphanData: OrphanJson | null = null
  try {
    const [graphHealthRaw, orphanRaw] = await Promise.all([
      runPythonTool(pythonBin, path.join(toolsDir, 'graph_health.py'), ['report', '--output', 'json', '--brain-path', brainPath], pmosPath),
      runPythonTool(pythonBin, path.join(toolsDir, 'orphan_analyzer.py'), ['scan', '--output', 'json', '--brain-path', brainPath], pmosPath),
    ])
    graphHealth = JSON.parse(graphHealthRaw)
    orphanData = JSON.parse(orphanRaw)
  } catch (e) {
    console.warn('[brain-health] Python tools failed:', (e as Error).message)
  }

  const orphansByReason: OrphanBreakdown[] = orphanData
    ? Object.entries(orphanData.orphans_by_reason || {}).map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count)
    : []

  const relationshipTypes: RelationshipTypeCount[] = graphHealth
    ? Object.entries(graphHealth.relationships_by_type || {}).map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count)
    : []

  // Fallback entity count from registry if Python tools failed
  let registryEntityCount = 0
  if (!graphHealth) {
    try {
      const registryPath = path.join(pmosPath, 'user', 'brain', 'registry.yaml')
      if (existsSync(registryPath)) {
        const regRaw = yaml.load(readFileSync(registryPath, 'utf-8')) as Record<string, any>
        const regEntities = regRaw.entities && typeof regRaw.entities === 'object' ? regRaw.entities : regRaw
        registryEntityCount = Object.values(regEntities).filter((e: any) => e && typeof e === 'object' && e.$type).length
      }
    } catch { /* ignore */ }
  }

  // Prefer Python tool output for all graph structure metrics; fall back to registry/defaults
  return {
    connectivityRate: graphHealth ? Math.round(graphHealth.relationship_coverage * 100) : 0,
    entityCount: graphHealth ? graphHealth.total_entities : registryEntityCount,
    medianRelationships: graphHealth?.median_relationships ?? Math.round((graphHealth?.avg_relationships_per_entity ?? 0) * 10) / 10,
    graphComponents: graphHealth?.connected_components ?? 0,
    graphDiameter: graphHealth?.graph_diameter ?? null,
    orphanCount: graphHealth ? graphHealth.orphan_entities : 0,
    orphanRate: orphanData ? Math.round(orphanData.orphan_rate * 10) / 10 : 0,
    orphansByReason,
    staleEntityRate: registryMetrics.staleEntityRate,
    enrichmentVelocity7d: registryMetrics.enrichmentVelocity7d,
    lastEnrichmentTimestamp: lastEnrichment,
    densityScore: graphHealth ? Math.round(graphHealth.density_score * 100) / 100 : 0,
    relationshipTypes,
    entitiesByType: graphHealth ? (graphHealth.entities_by_type || {}) : {},
    targets: configTargets,
  }
}

export function getSyntheticBrainHealth(): BrainHealthData {
  return {
    connectivityRate: 72,
    entityCount: 347,
    medianRelationships: 2.3,
    graphComponents: 3,
    graphDiameter: 8,
    orphanCount: 28,
    orphanRate: 8.1,
    orphansByReason: [
      { reason: 'pending_enrichment', count: 15 },
      { reason: 'no_external_data', count: 8 },
      { reason: 'standalone', count: 3 },
      { reason: 'enrichment_failed', count: 2 },
    ],
    staleEntityRate: 22,
    enrichmentVelocity7d: 6,
    lastEnrichmentTimestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    densityScore: 0.64,
    relationshipTypes: [
      { type: 'part_of', count: 89 },
      { type: 'owns', count: 67 },
      { type: 'member_of', count: 54 },
      { type: 'works_on', count: 41 },
      { type: 'related_to', count: 38 },
      { type: 'depends_on', count: 22 },
      { type: 'reports_to', count: 15 },
      { type: 'similar_to', count: 11 },
    ],
    entitiesByType: {
      project: 142, person: 68, team: 34, system: 28, brand: 22,
      experiment: 18, domain: 15, squad: 12, feature: 8,
    },
    targets: { ...DEFAULT_TARGETS },
  }
}
