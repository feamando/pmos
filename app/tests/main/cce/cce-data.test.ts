import { describe, it, expect, vi } from 'vitest'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
  shell: { openPath: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(_key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  },
}))

vi.mock('child_process', () => ({
  execFile: vi.fn(),
}))

import { getSyntheticCCEData, parseCCEJson, mergeWcrHighlights } from '../../../src/main/cce/cce-data'

describe('cce-data', () => {
  describe('getSyntheticCCEData', () => {
    it('returns valid CCEHubData structure', () => {
      const data = getSyntheticCCEData()
      expect(data.generatedAt).toBeTypeOf('string')
      expect(data.summary.products).toBeTypeOf('number')
      expect(data.summary.features).toBeTypeOf('number')
      expect(data.summary.active).toBeTypeOf('number')
      expect(data.products).toBeInstanceOf(Array)
    })

    it('contains products with varied statuses', () => {
      const data = getSyntheticCCEData()
      const allStatuses = data.products.flatMap((p) => p.features.map((f) => f.meta.status))
      expect(allStatuses.some((s) => s.toLowerCase().includes('progress'))).toBe(true)
      expect(allStatuses.some((s) => s.toLowerCase().includes('discovery'))).toBe(true)
      expect(allStatuses.some((s) => s === 'To Do')).toBe(true)
      expect(allStatuses.some((s) => s === 'Deprioritized')).toBe(true)
      expect(allStatuses.some((s) => s === 'Complete')).toBe(true)
    })

    it('includes WCR-highlighted and non-WCR products', () => {
      const data = getSyntheticCCEData()
      expect(data.products.some((p) => p.isWcrProduct)).toBe(true)
      expect(data.products.some((p) => !p.isWcrProduct)).toBe(true)
    })

    it('includes features with latest_action entries', () => {
      const data = getSyntheticCCEData()
      const withAction = data.products.flatMap((p) => p.features).filter((f) => f.meta.latestAction)
      const withoutAction = data.products.flatMap((p) => p.features).filter((f) => !f.meta.latestAction)
      expect(withAction.length).toBeGreaterThan(0)
      expect(withoutAction.length).toBeGreaterThan(0)
    })

    it('has correct summary counts', () => {
      const data = getSyntheticCCEData()
      const totalFeatures = data.products.reduce((sum, p) => sum + p.features.length, 0)
      expect(data.summary.features).toBe(totalFeatures)
      expect(data.summary.products).toBe(data.products.length)
    })

    it('includes wcrMeta for WCR products', () => {
      const data = getSyntheticCCEData()
      const wcrProduct = data.products.find((p) => p.isWcrProduct)!
      expect(wcrProduct.wcrMeta).toBeDefined()
      expect(wcrProduct.wcrMeta!.squad).toBeTypeOf('string')
      expect(wcrProduct.wcrMeta!.tribe).toBeTypeOf('string')
    })
  })

  describe('parseCCEJson', () => {
    it('parses valid JSON output from generator', () => {
      const raw = JSON.stringify({
        generated_at: '2026-03-30T09:00:00Z',
        summary: { products: 1, features: 1, active: 1 },
        products: [{
          id: 'test-product', name: 'Test Product', org: 'test-org', path: 'test-org/test-product',
          meta: { status: 'ACTIVE', owner: null, type: null, last_updated: null },
          features: [{
            id: 'test-feature', name: 'Test Feature', path: 'test-org/test-product/test-feature',
            meta: { title: 'Test Feature', status: 'In Progress', owner: 'Test User', priority: 'P0',
              deadline: null, last_updated: '2026-03-30', description: 'A test feature', action_count: 2,
              latest_action: { date: '2026-03-30', action: 'Updated specs', status: 'In Progress' } },
          }],
        }],
      })
      const parsed = parseCCEJson(raw)
      expect(parsed.products).toHaveLength(1)
      expect(parsed.products[0].features[0].meta.latest_action!.action).toBe('Updated specs')
    })

    it('throws on invalid JSON', () => {
      expect(() => parseCCEJson('not json')).toThrow()
    })
  })

  describe('mergeWcrHighlights', () => {
    it('returns products with isWcrProduct false when no WCR config', () => {
      const products = [{
        id: 'test', name: 'Test', org: 'org', path: 'org/test',
        meta: { status: null, owner: null, type: null, last_updated: null },
        features: [],
      }]
      // mergeWcrHighlights reads config internally, will fail gracefully
      const result = mergeWcrHighlights(products, '/nonexistent')
      expect(result).toHaveLength(1)
      expect(result[0].isWcrProduct).toBe(false)
    })
  })
})
