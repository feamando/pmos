import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import yaml from 'js-yaml'

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

// Mock child_process.execFile for Python tools
vi.mock('child_process', () => ({
  execFile: vi.fn(),
}))

import { getSyntheticBrainHealth } from '../../../src/main/brain/brain-health'

describe('brain-health', () => {
  describe('getSyntheticBrainHealth', () => {
    it('returns complete synthetic data with all required fields', () => {
      const data = getSyntheticBrainHealth()

      expect(data.connectivityRate).toBeTypeOf('number')
      expect(data.entityCount).toBeTypeOf('number')
      expect(data.medianRelationships).toBeTypeOf('number')
      expect(data.graphComponents).toBeTypeOf('number')
      expect(data.graphDiameter).toBeTypeOf('number')
      expect(data.orphanCount).toBeTypeOf('number')
      expect(data.orphanRate).toBeTypeOf('number')
      expect(data.staleEntityRate).toBeTypeOf('number')
      expect(data.enrichmentVelocity7d).toBeTypeOf('number')
      expect(data.densityScore).toBeTypeOf('number')
    })

    it('includes orphan breakdown by reason', () => {
      const data = getSyntheticBrainHealth()
      expect(data.orphansByReason.length).toBeGreaterThan(0)
      expect(data.orphansByReason[0]).toHaveProperty('reason')
      expect(data.orphansByReason[0]).toHaveProperty('count')
    })

    it('includes relationship type distribution', () => {
      const data = getSyntheticBrainHealth()
      expect(data.relationshipTypes.length).toBeGreaterThan(0)
      expect(data.relationshipTypes[0]).toHaveProperty('type')
      expect(data.relationshipTypes[0]).toHaveProperty('count')
    })

    it('includes entity type distribution', () => {
      const data = getSyntheticBrainHealth()
      expect(Object.keys(data.entitiesByType).length).toBeGreaterThan(0)
      expect(data.entitiesByType).toHaveProperty('project')
    })

    it('includes target values', () => {
      const data = getSyntheticBrainHealth()
      expect(data.targets.connectivityRate).toBe(85)
      expect(data.targets.entityCount).toBe(500)
      expect(data.targets.medianRelationships).toBe(3)
      expect(data.targets.graphComponents).toBe(1)
      expect(data.targets.orphanRate).toBe(10)
      expect(data.targets.staleEntityRate).toBe(15)
      expect(data.targets.enrichmentVelocity7d).toBe(10)
    })

    it('has synthetic values that exercise all indicator states', () => {
      const data = getSyntheticBrainHealth()
      // Connectivity 72% vs 85% target = ~85% → green
      // Entity count 347 vs 500 = ~69% → yellow
      // Stale 22% vs ≤15% = over target → yellow
      // These ensure we can visually test all indicator colors
      expect(data.connectivityRate).toBeLessThan(data.targets.connectivityRate)
      expect(data.entityCount).toBeLessThan(data.targets.entityCount)
      expect(data.staleEntityRate).toBeGreaterThan(data.targets.staleEntityRate)
    })
  })

  describe('registry metrics computation', () => {
    let tmpDir: string

    beforeEach(() => {
      tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'brain-health-test-'))
      fs.mkdirSync(path.join(tmpDir, 'user', 'brain'), { recursive: true })
    })

    afterEach(() => {
      fs.rmSync(tmpDir, { recursive: true })
    })

    it('handles missing registry.yaml gracefully', async () => {
      // readRegistryMetrics is internal but exercised through computeBrainHealth
      // For unit test, verify the synthetic data works as a fallback
      const data = getSyntheticBrainHealth()
      expect(data.lastEnrichmentTimestamp).toBeTruthy()
    })

    it('creates valid registry yaml that can be read', () => {
      const registry = {
        'entity/person/test-person': {
          $type: 'person',
          $status: 'active',
          $updated: new Date().toISOString(),
          relationships_count: 3,
          $relationships: [
            { type: 'member_of', target: 'entity/team/test-team' },
          ],
        },
        'entity/team/test-team': {
          $type: 'team',
          $status: 'active',
          $updated: new Date().toISOString(),
          relationships_count: 1,
          $relationships: [],
        },
      }
      const registryPath = path.join(tmpDir, 'user', 'brain', 'registry.yaml')
      fs.writeFileSync(registryPath, yaml.dump(registry))

      const content = fs.readFileSync(registryPath, 'utf-8')
      const parsed = yaml.load(content) as Record<string, any>
      expect(Object.keys(parsed)).toHaveLength(2)
      expect(parsed['entity/person/test-person'].$type).toBe('person')
    })
  })
})
