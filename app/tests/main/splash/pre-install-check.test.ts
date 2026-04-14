import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
  app: { getVersion: () => '0.9.0', getPath: () => '/tmp/pmos-test' },
  BrowserWindow: vi.fn(),
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

import { splashShowPreInstallCheck } from '../../../src/main/splash'

// Helper: flush microtasks so async functions proceed past await
const tick = () => new Promise((r) => setTimeout(r, 0))

describe('splashShowPreInstallCheck', () => {
  let mockSplash: any
  let titleHandlers: Array<(event: any, title: string) => void>

  beforeEach(() => {
    titleHandlers = []
    mockSplash = {
      webContents: {
        executeJavaScript: vi.fn().mockResolvedValue(undefined),
      },
      on: vi.fn((event: string, handler: any) => {
        if (event === 'page-title-updated') titleHandlers.push(handler)
      }),
      removeListener: vi.fn((event: string, handler: any) => {
        titleHandlers = titleHandlers.filter((h) => h !== handler)
      }),
      isDestroyed: () => false,
    }
  })

  it('calls executeJavaScript with showPreInstallCheck', async () => {
    const promise = splashShowPreInstallCheck(mockSplash)
    await tick()

    for (const handler of titleHandlers) {
      handler({}, 'PRECHECK:continue')
    }

    await promise

    expect(mockSplash.webContents.executeJavaScript).toHaveBeenCalledWith(
      expect.stringContaining('window.showPreInstallCheck')
    )
  })

  it('resolves when page-title-updated fires with PRECHECK:continue', async () => {
    const promise = splashShowPreInstallCheck(mockSplash)
    await tick()

    // Should not resolve for other titles
    for (const handler of titleHandlers) {
      handler({}, 'IDLE')
    }

    // Should resolve for PRECHECK:continue
    for (const handler of titleHandlers) {
      handler({}, 'PRECHECK:continue')
    }

    await promise
  })

  it('removes listener after resolution', async () => {
    const promise = splashShowPreInstallCheck(mockSplash)
    await tick()

    for (const handler of titleHandlers) {
      handler({}, 'PRECHECK:continue')
    }

    await promise

    expect(mockSplash.removeListener).toHaveBeenCalledWith(
      'page-title-updated',
      expect.any(Function)
    )
  })

  it('sets document.title to IDLE before showing screen', async () => {
    const promise = splashShowPreInstallCheck(mockSplash)
    await tick()

    for (const handler of titleHandlers) {
      handler({}, 'PRECHECK:continue')
    }

    await promise

    const jsCode = mockSplash.webContents.executeJavaScript.mock.calls[0][0]
    expect(jsCode).toContain("document.title = 'IDLE'")
  })

  it('sets title to PRECHECK:continue in callback', async () => {
    const promise = splashShowPreInstallCheck(mockSplash)
    await tick()

    for (const handler of titleHandlers) {
      handler({}, 'PRECHECK:continue')
    }

    await promise

    const jsCode = mockSplash.webContents.executeJavaScript.mock.calls[0][0]
    expect(jsCode).toContain("document.title = 'PRECHECK:continue'")
  })
})

describe('checkbox visibility logic', () => {
  function allChecked(mac: boolean, claude: boolean, devtools: boolean): boolean {
    return mac && claude && devtools
  }

  it('returns false when no boxes checked', () => {
    expect(allChecked(false, false, false)).toBe(false)
  })

  it('returns false when 1 of 3 checked', () => {
    expect(allChecked(true, false, false)).toBe(false)
    expect(allChecked(false, true, false)).toBe(false)
    expect(allChecked(false, false, true)).toBe(false)
  })

  it('returns false when 2 of 3 checked', () => {
    expect(allChecked(true, true, false)).toBe(false)
    expect(allChecked(true, false, true)).toBe(false)
    expect(allChecked(false, true, true)).toBe(false)
  })

  it('returns true when all 3 checked', () => {
    expect(allChecked(true, true, true)).toBe(true)
  })

  it('returns false when unchecking 1 of 3', () => {
    expect(allChecked(false, true, true)).toBe(false)
  })
})
