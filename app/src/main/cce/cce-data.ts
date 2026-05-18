import { execFile } from 'child_process'
import { existsSync } from 'fs'
import path from 'path'
import { readConfigYaml } from '../config-yaml-manager'
import type { CCEHubData, CCEProduct } from '../../shared/types'

interface GeneratorProduct {
  id: string
  name: string
  org: string
  path: string
  meta: { status: string | null; owner: string | null; type: string | null; last_updated: string | null }
  features: Array<{
    id: string
    name: string
    path: string
    meta: {
      title: string
      status: string
      owner: string | null
      priority: string | null
      deadline: string | null
      last_updated: string | null
      description: string | null
      action_count: number
      latest_action: { date: string; action: string; status: string } | null
    }
  }>
}

interface GeneratorOutput {
  generated_at: string
  summary: { products: number; features: number; active: number }
  products: GeneratorProduct[]
}

function getPythonBin(pmosPath: string): string {
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  return existsSync(venvPython) ? venvPython : 'python3'
}

function runGenerator(pmosPath: string): Promise<string> {
  const pythonBin = getPythonBin(pmosPath)
  const scriptPath = path.join(pmosPath, 'common', 'tools', 'features', 'feature_index_generator.py')
  const productsPath = path.join(pmosPath, 'user', 'products')

  return new Promise((resolve, reject) => {
    execFile(pythonBin, [scriptPath, '--format', 'json', '--products-path', productsPath], {
      timeout: 30000,
      env: { ...process.env, PM_OS_ROOT: pmosPath, PYTHONPATH: path.join(pmosPath, 'common', 'tools') },
    }, (err, stdout, stderr) => {
      if (err) reject(new Error(`${err.message}${stderr ? ': ' + stderr : ''}`))
      else resolve(stdout)
    })
  })
}

export function parseCCEJson(raw: string): GeneratorOutput {
  return JSON.parse(raw) as GeneratorOutput
}

export function mergeWcrHighlights(products: GeneratorProduct[], pmosPath: string): CCEProduct[] {
  let wcrProducts: Array<{ name?: string; jira_project?: string; squad?: string; tribe?: string; market?: string }> = []
  try {
    const config = readConfigYaml(pmosPath)
    wcrProducts = config?.wcr?.products || config?.products || []
    if (!Array.isArray(wcrProducts)) wcrProducts = []
  } catch { /* no WCR config */ }

  return products.map((p) => {
    const wcrMatch = wcrProducts.find((w) => {
      if (!w.name) return false
      const wName = w.name.toLowerCase()
      const pName = p.name.toLowerCase()
      const pId = p.id.toLowerCase()
      return pName.includes(wName) || wName.includes(pName) || pId.includes(wName.replace(/\s+/g, '-'))
    })

    return {
      id: p.id,
      name: p.name,
      org: p.org,
      path: p.path,
      meta: {
        status: p.meta.status,
        owner: p.meta.owner,
        type: p.meta.type,
        lastUpdated: p.meta.last_updated,
      },
      features: p.features.map((f) => ({
        id: f.id,
        name: f.name,
        path: f.path,
        meta: {
          title: f.meta.title,
          status: f.meta.status,
          owner: f.meta.owner,
          priority: f.meta.priority,
          deadline: f.meta.deadline,
          lastUpdated: f.meta.last_updated,
          description: f.meta.description,
          actionCount: f.meta.action_count,
          latestAction: f.meta.latest_action ? {
            date: f.meta.latest_action.date,
            action: f.meta.latest_action.action,
            status: f.meta.latest_action.status,
          } : null,
        },
      })),
      isWcrProduct: !!wcrMatch,
      wcrMeta: wcrMatch ? {
        squad: wcrMatch.squad,
        tribe: wcrMatch.tribe,
        market: wcrMatch.market,
      } : undefined,
    }
  })
}

export async function getCCEProjects(pmosPath: string): Promise<CCEHubData> {
  const raw = await runGenerator(pmosPath)
  const parsed = parseCCEJson(raw)
  const allProducts = mergeWcrHighlights(parsed.products, pmosPath)

  // Only show products tracked in config.yaml
  let trackedIds: string[] = []
  try {
    const config = readConfigYaml(pmosPath)
    const items = config?.products?.items || []
    if (Array.isArray(items)) {
      trackedIds = items
        .filter((i: any) => i.status === 'active')
        .map((i: any) => (i.id || '').toLowerCase())
    }
  } catch { /* no config — show all */ }

  const products = trackedIds.length > 0
    ? allProducts.filter((p) => trackedIds.includes(p.id.toLowerCase()))
    : allProducts

  const activeCount = products.reduce((sum, p) =>
    sum + p.features.filter((f) =>
      ['in progress', 'active', 'discovery', 'planning'].some((s) => (f.meta.status || '').toLowerCase().includes(s))
    ).length, 0)

  return {
    generatedAt: parsed.generated_at,
    summary: { products: products.length, features: products.reduce((s, p) => s + p.features.length, 0), active: activeCount },
    products,
  }
}

export function getSyntheticCCEData(): CCEHubData {
  return {
    generatedAt: new Date().toISOString(),
    summary: { products: 2, features: 5, active: 3 },
    products: [
      {
        id: 'sample-product',
        name: 'Sample Product',
        org: 'my-org',
        path: 'my-org/sample-product',
        meta: { status: 'ACTIVE', owner: 'Jane Doe', type: 'brand', lastUpdated: '2026-01-15' },
        features: [
          {
            id: 'onboarding-flow', name: 'Onboarding Flow Redesign', path: 'my-org/sample-product/onboarding-flow',
            meta: { title: 'Onboarding Flow Redesign', status: 'In Progress', owner: 'Jane Doe', priority: 'P0', deadline: '2026-02-01', lastUpdated: '2026-01-15', description: 'Redesign the onboarding experience for new users.', actionCount: 3, latestAction: { date: '2026-01-15', action: 'Completed user research', status: 'In Progress' } },
          },
          {
            id: 'search-feature', name: 'Search Feature', path: 'my-org/sample-product/search-feature',
            meta: { title: 'Search Feature', status: 'Planning', owner: 'John Smith', priority: 'P1', deadline: null, lastUpdated: '2026-01-10', description: 'Full-text search across product catalog.', actionCount: 1, latestAction: { date: '2026-01-10', action: 'Requirements gathering', status: 'Planning' } },
          },
        ],
        isWcrProduct: true,
        wcrMeta: { squad: 'Growth', tribe: 'Product', market: 'US' },
      },
      {
        id: 'platform',
        name: 'Platform',
        org: 'my-org',
        path: 'my-org/platform',
        meta: { status: 'ACTIVE', owner: null, type: null, lastUpdated: '2026-01-12' },
        features: [
          {
            id: 'api-v2', name: 'API v2 Migration', path: 'my-org/platform/api-v2',
            meta: { title: 'API v2 Migration', status: 'In Progress', owner: 'Alex Chen', priority: 'P0', deadline: '2026-03-01', lastUpdated: '2026-01-12', description: 'Migrate all endpoints to API v2 with improved auth.', actionCount: 5, latestAction: { date: '2026-01-12', action: 'Completed auth module', status: 'In Progress' } },
          },
          {
            id: 'monitoring', name: 'Observability Stack', path: 'my-org/platform/monitoring',
            meta: { title: 'Observability Stack', status: 'Discovery', owner: 'Alex Chen', priority: 'P1', deadline: null, lastUpdated: '2026-01-08', description: 'Unified logging, metrics, and tracing.', actionCount: 0, latestAction: null },
          },
          {
            id: 'ci-pipeline', name: 'CI Pipeline Optimization', path: 'my-org/platform/ci-pipeline',
            meta: { title: 'CI Pipeline Optimization', status: 'Complete', owner: 'John Smith', priority: 'P2', deadline: null, lastUpdated: '2026-01-05', description: 'Reduce CI build times from 12min to under 5min.', actionCount: 4, latestAction: { date: '2026-01-05', action: 'Deployed optimized pipeline', status: 'Complete' } },
          },
        ],
        isWcrProduct: false,
      },
    ],
  }
}
