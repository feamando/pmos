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
    summary: { products: 3, features: 9, active: 5 },
    products: [
      {
        id: 'product-alpha',
        name: 'Product Alpha Context',
        org: 'products',
        path: 'products/product-alpha',
        meta: { status: 'ACTIVE', owner: 'PM Lead', type: 'product', lastUpdated: '2026-03-27' },
        features: [
          {
            id: 'alpha-migration', name: 'Platform Migration Context', path: 'products/product-alpha/alpha-migration',
            meta: { title: 'Platform Migration Context', status: 'In Progress', owner: 'PM Lead', priority: 'P0', deadline: '2026-04-15', lastUpdated: '2026-03-28', description: 'Platform migration specs for Product Alpha.', actionCount: 5, latestAction: { date: '2026-03-28', action: 'Updated migration specs', status: 'In Progress' } },
          },
          {
            id: 'alpha-b2b', name: 'B2B Channel Context', path: 'products/product-alpha/alpha-b2b',
            meta: { title: 'B2B Channel Context', status: 'Planning', owner: 'Team Lead', priority: 'P0', deadline: '2026-04-01', lastUpdated: '2026-03-25', description: 'B2B channel strategy for Product Alpha market entry.', actionCount: 3, latestAction: { date: '2026-03-25', action: 'Drafted partner integration plan', status: 'Planning' } },
          },
          {
            id: 'alpha-onboarding', name: 'Onboarding Quiz / User Goals', path: 'products/product-alpha/alpha-onboarding',
            meta: { title: 'Onboarding Quiz / User Goals', status: 'Active — Initialization', owner: 'Product Manager', priority: 'P1', deadline: null, lastUpdated: '2026-03-13', description: 'User goals quiz for personalized onboarding funnel.', actionCount: 2, latestAction: null },
          },
        ],
        isWcrProduct: true,
        wcrMeta: { squad: 'Alpha Squad', tribe: 'Product', market: 'US' },
      },
      {
        id: 'product-beta',
        name: 'Product Beta Context',
        org: 'products',
        path: 'products/product-beta',
        meta: { status: 'ACTIVE', owner: null, type: 'product', lastUpdated: '2026-03-27' },
        features: [
          {
            id: 'beta-redesign', name: 'Product Beta Redesign Context', path: 'products/product-beta/beta-redesign',
            meta: { title: 'Product Beta Redesign Context', status: 'In Progress', owner: 'Team Lead', priority: 'P0', deadline: '2026-04-10', lastUpdated: '2026-03-27', description: 'UI redesign for Product Beta.', actionCount: 8, latestAction: { date: '2026-03-27', action: 'Completed design review', status: 'In Progress' } },
          },
          {
            id: 'beta-cross-sell', name: 'Cross-Sell Integration', path: 'products/product-beta/beta-cross-sell',
            meta: { title: 'Cross-Sell Integration', status: 'Context v2 — Deep Research Complete', owner: 'PM Lead', priority: 'P2', deadline: null, lastUpdated: '2026-03-03', description: 'Cross-selling products across product lines.', actionCount: 4, latestAction: { date: '2026-03-03', action: 'Deep research phase completed', status: 'Complete' } },
          },
          {
            id: 'beta-merchandising', name: 'Better Merchandising & Marketing Context', path: 'products/product-beta/beta-merchandising',
            meta: { title: 'Better Merchandising & Marketing Context', status: 'Deprioritized', owner: 'PM Lead', priority: 'P2', deadline: null, lastUpdated: '2026-02-25', description: 'Merchandising improvements for Product Beta pages.', actionCount: 0, latestAction: null },
          },
        ],
        isWcrProduct: true,
        wcrMeta: { squad: 'Beta Squad', tribe: 'Product', market: 'US' },
      },
      {
        id: 'product-gamma',
        name: 'Product Gamma Context',
        org: 'products',
        path: 'products/product-gamma',
        meta: { status: 'ACTIVE', owner: null, type: 'product', lastUpdated: '2026-03-27' },
        features: [
          {
            id: 'gamma-ai', name: 'AI Integrations Context', path: 'products/product-gamma/gamma-ai',
            meta: { title: 'AI Integrations Context', status: 'In Progress', owner: 'Product Manager', priority: 'P0', deadline: '2026-04-30', lastUpdated: '2026-03-27', description: 'AI integrations for product ecosystem.', actionCount: 6, latestAction: { date: '2026-03-27', action: 'Submitted integration for review', status: 'In Progress' } },
          },
          {
            id: 'gamma-api', name: 'API Integration', path: 'products/product-gamma/gamma-api',
            meta: { title: 'API Integration', status: 'In Progress — Parallel Tracks (Read-Only Phase 1)', owner: 'PM Lead', priority: 'P0', deadline: '2026-03-30', lastUpdated: '2026-02-26', description: 'Third-party API integration for data enrichment.', actionCount: 3, latestAction: { date: '2026-02-26', action: 'Completed read-only API integration', status: 'In Progress' } },
          },
          {
            id: 'gamma-compliance', name: 'Compliance Context', path: 'products/product-gamma/gamma-compliance',
            meta: { title: 'Compliance Context', status: 'In Discovery', owner: 'PM Lead', priority: 'P1', deadline: null, lastUpdated: '2026-03-27', description: 'Regulatory compliance integration.', actionCount: 1, latestAction: { date: '2026-03-27', action: 'Initial discovery research started', status: 'Discovery' } },
          },
        ],
        isWcrProduct: false,
      },
    ],
  }
}
