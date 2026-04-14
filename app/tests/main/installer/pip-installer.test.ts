import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('child_process', () => ({
  execFile: vi.fn(),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
}))

import { execFile } from 'child_process'
import { createVenv, installPipPackages, verifyCriticalPackages } from '../../../src/main/installer/pip-installer'

const mockExecFile = vi.mocked(execFile)

describe('pip-installer', () => {
  let testDir: string

  beforeEach(() => {
    vi.clearAllMocks()
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pip-test-'))
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  describe('createVenv', () => {
    it('creates a new venv successfully', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        // Simulate venv creation by creating the directory
        const venvPath = path.join(testDir, '.venv')
        fs.mkdirSync(venvPath, { recursive: true })
        callback(null, '', '')
        return {} as any
      })

      const result = await createVenv(testDir)
      expect(result.success).toBe(true)
    })

    it('skips if venv already exists', async () => {
      const venvPath = path.join(testDir, '.venv')
      fs.mkdirSync(venvPath, { recursive: true })

      const result = await createVenv(testDir)
      expect(result.success).toBe(true)
      expect(result.message).toContain('already exists')
      expect(mockExecFile).not.toHaveBeenCalled()
    })

    it('reports failure on venv creation error', async () => {
      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        callback(new Error('venv failed'), '', 'Error creating venv')
        return {} as any
      })

      const result = await createVenv(testDir)
      expect(result.success).toBe(false)
    })
  })

  describe('installPipPackages', () => {
    it('returns error when requirements.txt not found', async () => {
      const result = await installPipPackages(testDir, '/nonexistent/requirements.txt')
      expect(result.success).toBe(false)
      expect(result.message).toContain('not found')
    })

    it('returns error when pip not found', async () => {
      const reqPath = path.join(testDir, 'requirements.txt')
      fs.writeFileSync(reqPath, 'pyyaml\nrequests\n')

      const result = await installPipPackages(testDir, reqPath)
      expect(result.success).toBe(false)
      expect(result.message).toContain('pip not found')
    })

    it('installs packages successfully', async () => {
      // Create requirements and fake pip
      const reqPath = path.join(testDir, 'requirements.txt')
      fs.writeFileSync(reqPath, 'pyyaml\nrequests\n# comment\n\nslack-sdk\n')

      const pipPath = path.join(testDir, '.venv', 'bin')
      fs.mkdirSync(pipPath, { recursive: true })
      fs.writeFileSync(path.join(pipPath, 'pip'), '')

      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        callback(null, 'Successfully installed', '')
        return {} as any
      })

      const result = await installPipPackages(testDir, reqPath)
      expect(result.success).toBe(true)
      expect(result.message).toContain('3 packages')
    })
  })

  describe('verifyCriticalPackages', () => {
    it('verifies packages when all importable', async () => {
      const pythonDir = path.join(testDir, '.venv', 'bin')
      fs.mkdirSync(pythonDir, { recursive: true })
      fs.writeFileSync(path.join(pythonDir, 'python3'), '')

      mockExecFile.mockImplementation((cmd: any, args: any, opts: any, cb: any) => {
        const callback = typeof opts === 'function' ? opts : cb
        callback(null, '', '')
        return {} as any
      })

      const result = await verifyCriticalPackages(testDir)
      expect(result.success).toBe(true)
    })
  })
})
