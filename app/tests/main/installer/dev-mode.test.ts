import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as os from 'os'
import * as path from 'path'

// Mock electron + logger
vi.mock('electron', () => ({
  app: { getPath: () => os.tmpdir() },
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logWarn: vi.fn(),
}))

import { isDevMode, getDevPmosPath, cleanupDevInstall, getTargetPmosPath } from '../../../src/main/installer/dev-mode'

describe('dev-mode', () => {
  const origEnv = process.env.PMOS_DEV_MODE

  afterEach(() => {
    if (origEnv === undefined) delete process.env.PMOS_DEV_MODE
    else process.env.PMOS_DEV_MODE = origEnv
  })

  it('detects dev mode from env var', () => {
    process.env.PMOS_DEV_MODE = 'true'
    expect(isDevMode()).toBe(true)
  })

  it('returns false when env var not set', () => {
    delete process.env.PMOS_DEV_MODE
    expect(isDevMode()).toBe(false)
  })

  it('getDevPmosPath returns temp dir', () => {
    const devPath = getDevPmosPath()
    expect(devPath).toContain('pmos-dev')
    expect(devPath.startsWith(os.tmpdir())).toBe(true)
  })

  it('cleanupDevInstall removes temp dir', () => {
    const devPath = getDevPmosPath()
    fs.mkdirSync(path.join(devPath, 'user'), { recursive: true })
    expect(fs.existsSync(devPath)).toBe(true)

    const result = cleanupDevInstall()
    expect(result).toBe(true)
    expect(fs.existsSync(devPath)).toBe(false)
  })

  it('cleanupDevInstall returns false when nothing to clean', () => {
    const result = cleanupDevInstall()
    expect(result).toBe(false)
  })

  it('getTargetPmosPath returns dev path in dev mode', () => {
    process.env.PMOS_DEV_MODE = 'true'
    expect(getTargetPmosPath()).toContain('pmos-dev')
  })

  it('getTargetPmosPath returns home dir in normal mode', () => {
    delete process.env.PMOS_DEV_MODE
    expect(getTargetPmosPath()).toBe(path.join(os.homedir(), 'pm-os'))
  })
})
