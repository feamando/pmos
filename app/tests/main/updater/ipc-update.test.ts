import { describe, it, expect, vi } from 'vitest'

const mockHandle = vi.fn()
vi.mock('electron', () => ({
  app: { getVersion: () => '0.8.0-20260331', getPath: () => '/tmp/pmos-test' },
  ipcMain: { handle: mockHandle, on: vi.fn() },
  BrowserWindow: { getAllWindows: () => [] },
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

describe('updater IPC handlers', () => {
  it('get-app-version handler is registered via registerIpcHandlers', async () => {
    // Dynamic import after mocks are set
    const { registerIpcHandlers } = await import('../../../src/main/ipc-handlers')

    // Clear previous calls and register
    mockHandle.mockClear()
    // Note: registerIpcHandlers registers many handlers; we just verify the updater ones exist
    // We can't call it twice (duplicate handlers), so we check the mock was called with our channels
    registerIpcHandlers()

    const registeredChannels = mockHandle.mock.calls.map((c: any[]) => c[0])
    expect(registeredChannels).toContain('get-app-version')
    expect(registeredChannels).toContain('check-for-updates')
    expect(registeredChannels).toContain('start-update')
  })

  it('get-app-version returns version info', async () => {
    // Find the handler for get-app-version
    const handler = mockHandle.mock.calls.find((c: any[]) => c[0] === 'get-app-version')
    expect(handler).toBeDefined()

    const result = handler![1]()
    expect(result.version).toBe('0.8.0-20260331')
    // electronVersion comes from process.versions.electron which is undefined in test env
    expect(result).toHaveProperty('electronVersion')
  })
})
