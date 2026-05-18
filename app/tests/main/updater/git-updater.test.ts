import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('electron', () => ({
  app: { getVersion: () => '0.8.0', getPath: () => '/tmp/helloai-test' },
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

const mockExecFile = vi.fn()
vi.mock('child_process', () => ({
  execFile: (...args: any[]) => mockExecFile(...args),
}))

const mockExistsSync = vi.fn()
vi.mock('fs', async () => {
  const actual = await vi.importActual<typeof import('fs')>('fs')
  return { ...actual, existsSync: (...args: any[]) => mockExistsSync(...args) }
})

import { pullPmosRepo } from '../../../src/main/updater/git-updater'

describe('git-updater', () => {
  beforeEach(() => {
    mockExecFile.mockReset()
    mockExistsSync.mockReset()
    // By default, simulate .git exists at pmosPath (standard clone)
    mockExistsSync.mockImplementation((p: string) => p.endsWith('.git'))
  })

  it('returns error when pmosPath is empty', async () => {
    const result = await pullPmosRepo('')
    expect(result.success).toBe(false)
    expect(result.message).toBe('PM-OS path not configured')
  })

  it('runs git stash then pull then stash pop on success', async () => {
    mockExecFile
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'No local changes to save', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(new Error('not a symbolic ref'), '', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'Already up to date.\n', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'abc1234', ''))

    const result = await pullPmosRepo('/test/pm-os')
    expect(result.success).toBe(true)
    expect(result.message).toBe('Updated to abc1234')

    expect(mockExecFile).toHaveBeenCalledTimes(4)
    expect(mockExecFile.mock.calls[0][1]).toEqual(['stash'])
    expect(mockExecFile.mock.calls[1][1]).toEqual(['symbolic-ref', 'refs/remotes/origin/HEAD', '--short'])
    expect(mockExecFile.mock.calls[2][1]).toEqual(['pull', 'origin', 'master'])
    expect(mockExecFile.mock.calls[3][1]).toEqual(['rev-parse', '--short', 'HEAD'])
  })

  it('calls stash pop when local changes were stashed', async () => {
    mockExecFile
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'Saved working directory', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(new Error('not a symbolic ref'), '', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'Updating abc..def\n', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'def5678', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'Dropped refs/stash', ''))

    const result = await pullPmosRepo('/test/pm-os')
    expect(result.success).toBe(true)
    expect(mockExecFile).toHaveBeenCalledTimes(5)
    expect(mockExecFile.mock.calls[4][1]).toEqual(['stash', 'pop'])
  })

  it('returns failure on network error', async () => {
    mockExecFile
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(null, 'No local changes to save', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(new Error('not a symbolic ref'), '', ''))
      .mockImplementationOnce((_cmd: string, _args: string[], _opts: any, cb: any) => cb(new Error('fail'), '', 'Could not resolve host'))

    const result = await pullPmosRepo('/test/pm-os')
    expect(result.success).toBe(false)
    expect(result.message).toContain('Could not resolve host')
  })
})
