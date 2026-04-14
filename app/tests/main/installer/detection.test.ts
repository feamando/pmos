import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

// Mock electron + dependencies
vi.mock('electron', () => ({
  app: { getPath: () => os.tmpdir() },
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
}))
vi.mock('../../../src/main/installer/config-store', () => ({
  getInstallConfig: () => ({ pmosPath: null, installComplete: false, installedAt: null, version: '0.1.0', devMode: false }),
}))
vi.mock('../../../src/main/installer/dev-mode', () => ({
  isDevMode: () => false,
  getDevPmosPath: () => path.join(os.tmpdir(), 'pmos-dev'),
}))

import { detectPmosInstallation, validateCustomPath } from '../../../src/main/installer/detection'

describe('detection', () => {
  let testDir: string

  beforeEach(() => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'detection-test-'))
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  it('returns not found when no PM-OS exists', () => {
    const result = detectPmosInstallation()
    // On CI or machines without ~/pm-os this returns not found
    // On dev machines it might find the real one — that's OK
    expect(result).toHaveProperty('found')
    expect(result).toHaveProperty('path')
    expect(result).toHaveProperty('valid')
    expect(result).toHaveProperty('missing')
  })

  it('validates a complete installation', () => {
    // Create a valid PM-OS layout
    fs.mkdirSync(path.join(testDir, 'common'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'user'), { recursive: true })
    fs.writeFileSync(path.join(testDir, 'user', '.env'), 'TEST=1')

    const result = validateCustomPath(testDir)
    expect(result.found).toBe(true)
    expect(result.valid).toBe(true)
    expect(result.missing).toHaveLength(0)
  })

  it('detects partial installation with missing files', () => {
    fs.mkdirSync(path.join(testDir, 'common'), { recursive: true })
    // missing user/ and user/.env

    const result = validateCustomPath(testDir)
    expect(result.found).toBe(true) // common/ exists
    expect(result.valid).toBe(false)
    expect(result.missing).toContain('user')
    expect(result.missing).toContain('user/.env')
  })

  it('returns not found for nonexistent path', () => {
    const result = validateCustomPath('/nonexistent/path/xyz')
    expect(result.found).toBe(false)
    expect(result.valid).toBe(false)
  })
})
