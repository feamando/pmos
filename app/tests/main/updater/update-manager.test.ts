import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
  app: { getVersion: () => '0.8.0', getPath: () => '/tmp/pmos-test', relaunch: vi.fn(), exit: vi.fn() },
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

import { readManifest, isNewerVersion, checkForUpdates } from '../../../src/main/updater/update-manager'
import type { UpdateManifest } from '../../../src/shared/types'

describe('update-manager', () => {
  describe('isNewerVersion', () => {
    it('detects newer major version', () => {
      expect(isNewerVersion('0.8.0', '1.0.0')).toBe(true)
    })

    it('detects newer minor version', () => {
      expect(isNewerVersion('0.8.0', '0.9.0')).toBe(true)
    })

    it('detects newer patch version', () => {
      expect(isNewerVersion('0.8.0', '0.8.1')).toBe(true)
    })

    it('returns false for same version', () => {
      expect(isNewerVersion('0.8.0', '0.8.0')).toBe(false)
    })

    it('returns false for older version', () => {
      expect(isNewerVersion('0.9.0', '0.8.0')).toBe(false)
    })

    it('compares date stamps when semver is equal', () => {
      expect(isNewerVersion('0.8.0-20260331', '0.8.0-20260401')).toBe(true)
    })

    it('returns false for same date stamp', () => {
      expect(isNewerVersion('0.8.0-20260331', '0.8.0-20260331')).toBe(false)
    })

    it('returns false for older date stamp', () => {
      expect(isNewerVersion('0.8.0-20260401', '0.8.0-20260331')).toBe(false)
    })

    it('manifest with date is newer than current without date', () => {
      expect(isNewerVersion('0.8.0', '0.8.0-20260331')).toBe(true)
    })

    it('strips leading v prefix', () => {
      expect(isNewerVersion('v0.8.0', '0.9.0')).toBe(true)
    })
  })

  describe('checkForUpdates', () => {
    it('returns error when manifest not found', () => {
      const result = checkForUpdates('/nonexistent/path', '0.8.0')
      expect(result.available).toBe(false)
      expect(result.error).toBeDefined()
    })
  })

  describe('readManifest', () => {
    it('throws when manifest path does not exist', () => {
      expect(() => readManifest('/nonexistent/path')).toThrow('Update manifest not found')
    })
  })
})
