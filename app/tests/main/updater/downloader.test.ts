import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { createHash } from 'crypto'
import { writeFileSync, mkdirSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import path from 'path'

vi.mock('electron', () => ({
  app: { getVersion: () => '0.8.0', getPath: () => '/tmp/pmos-test' },
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

import { verifyChecksum } from '../../../src/main/updater/downloader'

describe('downloader', () => {
  const testDir = path.join(tmpdir(), 'pmos-downloader-test')
  const testFile = path.join(testDir, 'test-file.bin')
  const testContent = 'hello world test content'
  const expectedHash = createHash('sha256').update(testContent).digest('hex')

  beforeAll(() => {
    mkdirSync(testDir, { recursive: true })
    writeFileSync(testFile, testContent)
  })

  afterAll(() => {
    rmSync(testDir, { recursive: true, force: true })
  })

  describe('verifyChecksum', () => {
    it('returns valid for matching hash', async () => {
      const result = await verifyChecksum(testFile, expectedHash)
      expect(result.valid).toBe(true)
      expect(result.actual).toBe(expectedHash)
    })

    it('returns invalid for mismatched hash', async () => {
      const result = await verifyChecksum(testFile, 'deadbeef')
      expect(result.valid).toBe(false)
      expect(result.actual).toBe(expectedHash)
    })

    it('throws for missing file', async () => {
      await expect(verifyChecksum('/nonexistent/file', 'abc')).rejects.toThrow('File not found')
    })
  })
})
