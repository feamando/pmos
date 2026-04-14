import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))

import { createFolderStructure, distributeGoogleCredentials } from '../../../src/main/installer/scaffolder'

describe('scaffolder', () => {
  let testDir: string

  beforeEach(() => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'scaffold-test-'))
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  describe('createFolderStructure', () => {
    it('creates the full directory tree', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      const result = await createFolderStructure(pmosPath)

      expect(result.success).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, '.pm-os-root'))).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, 'common'))).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, 'user'))).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, 'user', 'brain', 'Entities'))).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, 'user', '.secrets'))).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, '.claude'))).toBe(true)
    })

    it('sets .secrets permissions to 0700', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      await createFolderStructure(pmosPath)

      const stats = fs.statSync(path.join(pmosPath, 'user', '.secrets'))
      expect(stats.mode & 0o777).toBe(0o700)
    })

    it('is idempotent — re-running does not fail', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      const r1 = await createFolderStructure(pmosPath)
      const r2 = await createFolderStructure(pmosPath)

      expect(r1.success).toBe(true)
      expect(r2.success).toBe(true)
    })

    it('creates .pm-os-root marker file', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      await createFolderStructure(pmosPath)

      const marker = fs.readFileSync(path.join(pmosPath, '.pm-os-root'), 'utf-8')
      expect(marker).toContain('pm-os-root')
    })
  })

  describe('distributeGoogleCredentials', () => {
    it('copies credentials from bundle to .secrets', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      const bundlePath = path.join(testDir, 'bundle')

      // Create source credentials
      const srcDir = path.join(bundlePath, 'data')
      fs.mkdirSync(srcDir, { recursive: true })
      fs.writeFileSync(path.join(srcDir, 'google_client_secret.json'), '{"installed":{"client_id":"test"}}')

      // Create target directory
      fs.mkdirSync(path.join(pmosPath, 'user', '.secrets'), { recursive: true })

      const result = await distributeGoogleCredentials(pmosPath, bundlePath)
      expect(result.success).toBe(true)
      expect(fs.existsSync(path.join(pmosPath, 'user', '.secrets', 'credentials.json'))).toBe(true)
    })

    it('skips when no bundled credentials exist', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      const bundlePath = path.join(testDir, 'bundle')
      fs.mkdirSync(bundlePath, { recursive: true })

      const result = await distributeGoogleCredentials(pmosPath, bundlePath)
      expect(result.success).toBe(true)
      expect(result.message).toContain('No')
    })

    it('skips when credentials already exist', async () => {
      const pmosPath = path.join(testDir, 'pmos')
      const bundlePath = path.join(testDir, 'bundle')

      fs.mkdirSync(path.join(bundlePath, 'data'), { recursive: true })
      fs.writeFileSync(path.join(bundlePath, 'data', 'google_client_secret.json'), '{"test":true}')

      const destDir = path.join(pmosPath, 'user', '.secrets')
      fs.mkdirSync(destDir, { recursive: true })
      fs.writeFileSync(path.join(destDir, 'credentials.json'), '{"existing":true}')

      const result = await distributeGoogleCredentials(pmosPath, bundlePath)
      expect(result.success).toBe(true)
      expect(result.message).toContain('Already')
    })
  })
})
