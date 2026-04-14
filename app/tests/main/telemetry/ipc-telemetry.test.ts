import { describe, it, expect, vi } from 'vitest'
import * as path from 'path'
import * as os from 'os'

const mockHandle = vi.fn()
const mockOn = vi.fn()

vi.mock('electron', () => ({
  app: { getVersion: () => '0.10.0-20260331', getPath: () => path.join(os.tmpdir(), 'pmos-ipc-test') },
  ipcMain: { handle: mockHandle, on: mockOn, removeHandler: vi.fn() },
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

describe('telemetry IPC handlers', () => {
  it('get-diagnostic-bundle and log-telemetry-click are registered', async () => {
    const { registerIpcHandlers } = await import('../../../src/main/ipc-handlers')
    mockHandle.mockClear()
    mockOn.mockClear()
    registerIpcHandlers()

    const handleChannels = mockHandle.mock.calls.map((c: any[]) => c[0])
    expect(handleChannels).toContain('get-diagnostic-bundle')

    const onChannels = mockOn.mock.calls.map((c: any[]) => c[0])
    expect(onChannels).toContain('log-telemetry-click')
  })

  it('get-diagnostic-bundle returns success with data string', async () => {
    const handler = mockHandle.mock.calls.find((c: any[]) => c[0] === 'get-diagnostic-bundle')
    expect(handler).toBeDefined()

    const result = await handler![1]()
    expect(result.success).toBe(true)
    expect(typeof result.data).toBe('string')
    expect(result.data).toContain('--- PM-OS Diagnostic ---')
  })

  it('log-telemetry-click calls handler without error', () => {
    const handler = mockOn.mock.calls.find((c: any[]) => c[0] === 'log-telemetry-click')
    expect(handler).toBeDefined()

    // Should not throw
    expect(() => handler![1]({}, 'test_click')).not.toThrow()
  })
})
