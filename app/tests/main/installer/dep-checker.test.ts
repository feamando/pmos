import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('child_process', () => ({
  execFile: vi.fn(),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
}))

import { execFile } from 'child_process'
import { checkPython, checkPip, checkXcodeTools, checkGit, checkAllDeps } from '../../../src/main/installer/dep-checker'

const mockExecFile = vi.mocked(execFile)

function setupExec(responses: Record<string, { stdout?: string; err?: Error | null }>) {
  mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
    const callback = typeof opts === 'function' ? opts : cb
    const key = `${cmd} ${Array.isArray(args) ? args.join(' ') : ''}`

    for (const [pattern, resp] of Object.entries(responses)) {
      if (key.includes(pattern)) {
        callback(resp.err || null, resp.stdout || '', '')
        return {} as any
      }
    }
    // Default: command not found
    callback(new Error('not found'), '', '')
    return {} as any
  })
}

describe('dep-checker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('checkPython', () => {
    it('finds python3 with valid version', async () => {
      setupExec({
        'python3 --version': { stdout: 'Python 3.12.7' },
        'which python3': { stdout: '/usr/bin/python3' },
      })
      const result = await checkPython()
      expect(result.found).toBe(true)
      expect(result.version).toBe('3.12.7')
    })

    it('rejects python below 3.10', async () => {
      setupExec({
        'python3 --version': { stdout: 'Python 3.9.1' },
        '/usr/bin/python3 --version': { stdout: 'Python 3.9.1' },
        '/usr/local/bin/python3 --version': { err: new Error('not found') },
        '/opt/homebrew/bin/python3 --version': { err: new Error('not found') },
      })
      const result = await checkPython()
      expect(result.found).toBe(false)
    })

    it('returns not found when no python available', async () => {
      setupExec({})
      const result = await checkPython()
      expect(result.found).toBe(false)
      expect(result.version).toBeNull()
      expect(result.path).toBeNull()
    })
  })

  describe('checkPip', () => {
    it('finds pip3', async () => {
      setupExec({
        'pip3 --version': { stdout: 'pip 24.0 from /usr/lib/python3.12/site-packages' },
        'which pip3': { stdout: '/usr/bin/pip3' },
      })
      const result = await checkPip()
      expect(result.found).toBe(true)
    })

    it('returns not found when pip missing', async () => {
      setupExec({})
      const result = await checkPip()
      expect(result.found).toBe(false)
    })
  })

  describe('checkXcodeTools', () => {
    it('detects installed xcode tools', async () => {
      setupExec({
        'xcode-select -p': { stdout: '/Library/Developer/CommandLineTools' },
      })
      const result = await checkXcodeTools()
      expect(result).toBe(true)
    })

    it('detects missing xcode tools', async () => {
      setupExec({})
      const result = await checkXcodeTools()
      expect(result).toBe(false)
    })
  })

  describe('checkGit', () => {
    it('detects git', async () => {
      setupExec({
        'git --version': { stdout: 'git version 2.39.3' },
      })
      const result = await checkGit()
      expect(result).toBe(true)
    })
  })

  describe('checkAllDeps', () => {
    it('runs all checks in parallel', async () => {
      setupExec({
        'python3 --version': { stdout: 'Python 3.12.7' },
        'which python3': { stdout: '/usr/bin/python3' },
        'pip3 --version': { stdout: 'pip 24.0' },
        'which pip3': { stdout: '/usr/bin/pip3' },
        'xcode-select -p': { stdout: '/Library/Developer/CommandLineTools' },
        'git --version': { stdout: 'git version 2.39.3' },
      })
      const result = await checkAllDeps()
      expect(result).toHaveProperty('python')
      expect(result).toHaveProperty('pip')
      expect(result).toHaveProperty('xcode')
      expect(result).toHaveProperty('git')
    })
  })
})
