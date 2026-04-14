import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn(), removeHandler: vi.fn() },
  BrowserWindow: { getAllWindows: () => [] },
}))

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
  },
}))

import { getInstallConfig, setInstallConfig, resetInstallConfig } from '../../../src/main/installer/config-store'

describe('v0.3 app-mode three-phase state machine', () => {
  beforeEach(() => {
    resetInstallConfig()
  })

  it('returns onboarding when installComplete but not onboardingComplete', () => {
    setInstallConfig({ installComplete: true })
    const config = getInstallConfig()
    let mode: string
    if (config.installComplete && !config.onboardingComplete) mode = 'onboarding'
    else if (config.onboardingComplete && !config.userSetupComplete) mode = 'user-setup'
    else mode = 'connections'
    expect(mode).toBe('onboarding')
  })

  it('returns user-setup when onboardingComplete but not userSetupComplete', () => {
    setInstallConfig({ installComplete: true, onboardingComplete: true })
    const config = getInstallConfig()
    let mode: string
    if (config.installComplete && !config.onboardingComplete) mode = 'onboarding'
    else if (config.onboardingComplete && !config.userSetupComplete) mode = 'user-setup'
    else mode = 'connections'
    expect(mode).toBe('user-setup')
  })

  it('returns connections when all three flags are true', () => {
    setInstallConfig({ installComplete: true, onboardingComplete: true, userSetupComplete: true })
    const config = getInstallConfig()
    let mode: string
    if (config.installComplete && !config.onboardingComplete) mode = 'onboarding'
    else if (config.onboardingComplete && !config.userSetupComplete) mode = 'user-setup'
    else mode = 'connections'
    expect(mode).toBe('connections')
  })

  it('defaults userSetupComplete to false', () => {
    const config = getInstallConfig()
    expect(config.userSetupComplete).toBe(false)
  })
})
