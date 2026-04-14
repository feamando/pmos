import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import yaml from 'js-yaml'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(_key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  },
}))

import { readConfigYaml, writeConfigYaml, validateConfigYaml } from '../../../src/main/config-yaml-manager'

describe('config-yaml-manager', () => {
  let tmpDir: string

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'config-yaml-test-'))
    fs.mkdirSync(path.join(tmpDir, 'user'), { recursive: true })
  })

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true })
  })

  it('returns empty object when config.yaml does not exist', () => {
    const result = readConfigYaml(tmpDir)
    expect(result).toEqual({})
  })

  it('reads existing config.yaml', () => {
    const content = yaml.dump({ version: '3.0.0', user: { name: 'Test' } })
    fs.writeFileSync(path.join(tmpDir, 'user', 'config.yaml'), content)
    const result = readConfigYaml(tmpDir)
    expect(result.version).toBe('3.0.0')
    expect(result.user.name).toBe('Test')
  })

  it('writes and merges config.yaml preserving existing fields', () => {
    const initial = { version: '3.0.0', user: { name: 'Test', email: 'test@test.com' }, brain: { hot_topics_limit: 10 } }
    fs.writeFileSync(path.join(tmpDir, 'user', 'config.yaml'), yaml.dump(initial))

    writeConfigYaml(tmpDir, { user: { name: 'Updated' }, brain: { workers: 5 } })

    const result = readConfigYaml(tmpDir)
    expect(result.user.name).toBe('Updated')
    expect(result.user.email).toBe('test@test.com') // preserved
    expect(result.brain.hot_topics_limit).toBe(10) // preserved
    expect(result.brain.workers).toBe(5) // new
  })

  it('adds version 3.0.0 if missing', () => {
    writeConfigYaml(tmpDir, { user: { name: 'Test' } })
    const result = readConfigYaml(tmpDir)
    expect(result.version).toBe('3.0.0')
  })

  it('overwrites arrays instead of merging them', () => {
    const initial = { integrations: { jira: { tracked_projects: ['OLD'] } } }
    fs.writeFileSync(path.join(tmpDir, 'user', 'config.yaml'), yaml.dump(initial))

    writeConfigYaml(tmpDir, { integrations: { jira: { tracked_projects: ['NEW1', 'NEW2'] } } })

    const result = readConfigYaml(tmpDir)
    expect(result.integrations.jira.tracked_projects).toEqual(['NEW1', 'NEW2'])
  })

  it('validates config with required fields present', () => {
    const result = validateConfigYaml({ user: { name: 'Test', email: 'test@test.com' } })
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('validates config with missing required fields', () => {
    const result = validateConfigYaml({ user: { name: '' } })
    expect(result.valid).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
  })

  it('returns warnings for missing optional sections', () => {
    const result = validateConfigYaml({ user: { name: 'Test', email: 'test@test.com' } })
    expect(result.warnings.length).toBeGreaterThan(0)
    expect(result.warnings.some(w => w.includes('Brain'))).toBe(true)
  })
})
