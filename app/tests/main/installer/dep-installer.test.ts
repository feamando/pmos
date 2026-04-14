import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('child_process', () => ({
  execFile: vi.fn(),
  spawn: vi.fn(() => ({ unref: vi.fn() })),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
}))

import { execFile } from 'child_process'
import { installXcodeTools, installPython, installPip } from '../../../src/main/installer/dep-installer'

const mockExecFile = vi.mocked(execFile)

describe('dep-installer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  describe('installPython', () => {
    it('installs via homebrew when available', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        if (cmd === 'which' && args[0] === 'brew') {
          callback(null, '/opt/homebrew/bin/brew', '')
        } else if (cmd === 'brew' && args[0] === 'install') {
          callback(null, 'installed', '')
        } else {
          callback(new Error('not found'), '', '')
        }
        return {} as any
      })

      const result = await installPython()
      expect(result.success).toBe(true)
      expect(result.message).toContain('Homebrew')
    })

    it('returns failure when brew install fails and download fails', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        if (cmd === 'which' && args[0] === 'brew') {
          callback(null, '/opt/homebrew/bin/brew', '')
        } else if (cmd === 'brew') {
          callback(new Error('failed'), '', 'brew error')
        } else if (cmd === 'curl') {
          callback(new Error('download failed'), '', 'curl error')
        } else {
          callback(new Error('not found'), '', '')
        }
        return {} as any
      })

      const result = await installPython()
      expect(result.success).toBe(false)
    })
  })

  describe('installPip', () => {
    it('runs ensurepip successfully', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        callback(null, 'pip installed', '')
        return {} as any
      })

      const result = await installPip()
      expect(result.success).toBe(true)
    })

    it('reports failure on ensurepip error', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        callback(new Error('failed'), '', 'ensurepip error')
        return {} as any
      })

      const result = await installPip()
      expect(result.success).toBe(false)
    })
  })
})
