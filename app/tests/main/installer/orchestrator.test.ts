import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock all dependencies
vi.mock('electron', () => ({
  BrowserWindow: vi.fn(),
}))
vi.mock('../../../src/main/installer/dep-checker', () => ({
  checkAllDeps: vi.fn(() => ({ python: { found: true, version: '3.12', path: '/usr/bin/python3' }, pip: { found: true, path: '/usr/bin/pip3' }, xcode: true, git: true })),
}))
vi.mock('../../../src/main/installer/dep-installer', () => ({
  installXcodeTools: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
  installPython: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
  installPip: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
}))
vi.mock('../../../src/main/installer/pip-installer', () => ({
  createVenv: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
  installPipPackages: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
  verifyCriticalPackages: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
}))
vi.mock('../../../src/main/installer/scaffolder', () => ({
  createFolderStructure: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
  distributeGoogleCredentials: vi.fn(() => ({ success: true, message: 'ok', duration: 0 })),
}))
vi.mock('../../../src/main/installer/config-generator', () => ({
  generateConfigFiles: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
}))
vi.mock('../../../src/main/installer/distributor', () => ({
  distributePmos: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
}))
vi.mock('../../../src/main/installer/post-setup', () => ({
  runPostSetup: vi.fn(() => ({ success: true, message: 'ok', duration: 1 })),
}))
vi.mock('../../../src/main/installer/verifier', () => ({
  runVerification: vi.fn(() => ({ success: true, checks: [], duration: 1 })),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))
vi.mock('../../../src/main/installer/dev-mode', () => ({
  isDevMode: () => false,
  getTargetPmosPath: () => '/tmp/test-pmos',
}))
vi.mock('../../../src/main/installer/config-store', () => ({
  setInstallConfig: vi.fn(),
}))
vi.mock('../../../src/main/splash', () => ({
  splashShowProgress: vi.fn(),
  splashUpdateProgress: vi.fn(),
  splashShowSuccess: vi.fn(),
  splashShowError: vi.fn(),
}))
vi.mock('fs', async () => {
  const actual = await vi.importActual('fs')
  return {
    ...actual,
    existsSync: vi.fn((p: string) => {
      if (p.includes('bundle')) return true
      return (actual as any).existsSync(p)
    }),
  }
})

import { runInstallation } from '../../../src/main/installer/orchestrator'
import { checkAllDeps } from '../../../src/main/installer/dep-checker'
import { createVenv } from '../../../src/main/installer/pip-installer'
import { runVerification } from '../../../src/main/installer/verifier'

describe('orchestrator', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('completes a full installation successfully', async () => {
    const result = await runInstallation(null)
    expect(result.success).toBe(true)
    expect(result.errors).toHaveLength(0)
    expect(result.pmosPath).toBe('/tmp/test-pmos')
  })

  it('reports progress via callbacks', async () => {
    const progressCalls: any[] = []
    const callbacks = {
      onProgress: (step: number, total: number, name: string, pct: number, steps: any[]) => {
        progressCalls.push({ step, total, name, pct })
      },
      onComplete: vi.fn(),
    }

    await runInstallation(null, callbacks)
    expect(progressCalls.length).toBeGreaterThan(0)
    expect(callbacks.onComplete).toHaveBeenCalled()
  })

  it('stops on critical dependency failure', async () => {
    vi.mocked(checkAllDeps).mockResolvedValueOnce({
      python: { found: false, version: null, path: null },
      pip: { found: false, path: null },
      xcode: false,
      git: true,
    })

    // Mock installers to fail
    const { installXcodeTools } = await import('../../../src/main/installer/dep-installer')
    vi.mocked(installXcodeTools).mockResolvedValueOnce({ success: false, message: 'Xcode install failed', duration: 1 })

    const result = await runInstallation(null)
    expect(result.success).toBe(false)
    expect(result.errors.length).toBeGreaterThan(0)
  })

  it('collects verification failures', async () => {
    vi.mocked(runVerification).mockResolvedValueOnce({
      success: false,
      checks: [
        { name: 'test-check', category: 'structure', passed: false, message: 'Missing file', duration: 0 },
      ],
      duration: 1,
    })

    const result = await runInstallation(null)
    expect(result.success).toBe(false)
    expect(result.errors.some((e) => e.includes('Verify failed'))).toBe(true)
  })
})
