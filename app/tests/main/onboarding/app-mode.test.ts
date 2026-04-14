import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock electron modules
vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn(), removeHandler: vi.fn() },
  BrowserWindow: { getAllWindows: () => [] },
}))

// Hoist shared state so it's available inside the mock factory
const { storeData } = vi.hoisted(() => {
  const storeData: Record<string, any> = {}
  return { storeData }
})

vi.mock('electron-store', () => ({
  default: class MockStore {
    private defaults: Record<string, any>
    constructor(opts: any) {
      this.defaults = opts?.defaults || {}
      for (const [k, v] of Object.entries(this.defaults)) {
        if (!(k in storeData)) storeData[k] = v
      }
    }
    get(key: string, fallback?: any) {
      if (key in storeData) return storeData[key]
      if (fallback !== undefined) return fallback
      return this.defaults[key]
    }
    set(key: string, value: any) { storeData[key] = value }
    clear() { for (const k of Object.keys(storeData)) delete storeData[k] }
  }
}))

import { getInstallConfig, setInstallConfig, resetInstallConfig } from '../../../src/main/installer/config-store'

describe('app-mode IPC logic', () => {
  beforeEach(() => {
    resetInstallConfig()
  })

  it('defaults to installComplete=false and onboardingComplete=false', () => {
    const config = getInstallConfig()
    expect(config.installComplete).toBe(false)
    expect(config.onboardingComplete).toBe(false)
  })

  it('returns onboarding mode when install complete but onboarding not', () => {
    setInstallConfig({ installComplete: true })
    const config = getInstallConfig()
    const mode = config.installComplete && !config.onboardingComplete ? 'onboarding' : 'connections'
    expect(mode).toBe('onboarding')
  })

  it('returns connections mode when both complete', () => {
    setInstallConfig({ installComplete: true, onboardingComplete: true })
    const config = getInstallConfig()
    const mode = config.installComplete && !config.onboardingComplete ? 'onboarding' : 'connections'
    expect(mode).toBe('connections')
  })

  it('complete-onboarding sets flag correctly', () => {
    setInstallConfig({ installComplete: true })
    setInstallConfig({ onboardingComplete: true })
    const config = getInstallConfig()
    expect(config.onboardingComplete).toBe(true)
    const mode = config.installComplete && !config.onboardingComplete ? 'onboarding' : 'connections'
    expect(mode).toBe('connections')
  })
})
