import { describe, it, expect, vi, beforeEach } from 'vitest'

const { _store } = vi.hoisted(() => {
  const _store: Record<string, any> = {}
  return { _store }
})

vi.mock('electron-store', () => {
  return {
    default: class {
      constructor(opts: any) {
        if (opts?.defaults) {
          for (const [k, v] of Object.entries(opts.defaults)) {
            if (!(k in _store)) _store[k] = v
          }
        }
      }
      get(key: string) { return _store[key] }
      set(key: string, value: any) { _store[key] = value }
      clear() { for (const k of Object.keys(_store)) delete _store[k] }
    },
  }
})

import { getInstallConfig, setInstallConfig, resetInstallConfig } from '../../../src/main/installer/config-store'

describe('config-store', () => {
  beforeEach(() => {
    for (const k of Object.keys(_store)) delete _store[k]
    _store.pmosPath = null
    _store.installComplete = false
    _store.installedAt = null
    _store.version = '0.1.0'
    _store.devMode = false
  })

  it('returns default config', () => {
    const config = getInstallConfig()
    expect(config.pmosPath).toBeNull()
    expect(config.installComplete).toBe(false)
    expect(config.version).toBe('0.1.0')
    expect(config.devMode).toBe(false)
  })

  it('updates partial config', () => {
    setInstallConfig({ pmosPath: '/test/pm-os', installComplete: true })
    const config = getInstallConfig()
    expect(config.pmosPath).toBe('/test/pm-os')
    expect(config.installComplete).toBe(true)
    expect(config.version).toBe('0.1.0')
  })

  it('resets config', () => {
    setInstallConfig({ pmosPath: '/test', devMode: true })
    resetInstallConfig()
    expect(Object.keys(_store)).toHaveLength(0)
  })
})
