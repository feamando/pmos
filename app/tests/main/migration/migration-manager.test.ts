import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, writeFileSync, rmSync } from 'fs'
import path from 'path'
import os from 'os'
import { detectV4Installation } from '../../../src/main/migration-manager'

let tmpDir: string

function makeTmpDir(): string {
  const dir = path.join(os.tmpdir(), `pmos-mig-test-${Date.now()}-${Math.random().toString(36).slice(2)}`)
  mkdirSync(dir, { recursive: true })
  return dir
}

beforeEach(() => {
  tmpDir = makeTmpDir()
})

afterEach(() => {
  rmSync(tmpDir, { recursive: true, force: true })
})

describe('migration-manager', () => {
  describe('detectV4Installation', () => {
    it('returns isV4: false for empty directory', () => {
      const result = detectV4Installation(tmpDir)
      expect(result.isV4).toBe(false)
    })

    it('returns isV4: false for empty string', () => {
      const result = detectV4Installation('')
      expect(result.isV4).toBe(false)
    })

    it('detects v4.x when brain.md command exists but no v5 plugins', () => {
      const cmdDir = path.join(tmpDir, 'common', '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'brain.md'), '# brain')

      const result = detectV4Installation(tmpDir)
      expect(result.isV4).toBe(true)
      expect(result.path).toBe(tmpDir)
    })

    it('returns isV4: false when v5 base plugin.json exists and is installed', () => {
      // v4 marker
      const cmdDir = path.join(tmpDir, 'common', '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'brain.md'), '# brain')

      // v5 marker
      const v5Dir = path.join(tmpDir, 'v5', 'plugins', 'pm-os-base', '.claude-plugin')
      mkdirSync(v5Dir, { recursive: true })
      writeFileSync(path.join(v5Dir, 'plugin.json'), '{}')

      // v5 base command registered
      const userCmdDir = path.join(tmpDir, '.claude', 'commands')
      mkdirSync(userCmdDir, { recursive: true })
      writeFileSync(path.join(userCmdDir, 'base.md'), '# base')

      const result = detectV4Installation(tmpDir)
      expect(result.isV4).toBe(false)
    })

    it('detects v4.x when v5 plugins exist but commands not registered', () => {
      // v4 marker
      const cmdDir = path.join(tmpDir, 'common', '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'brain.md'), '# brain')

      // v5 marker exists
      const v5Dir = path.join(tmpDir, 'v5', 'plugins', 'pm-os-base', '.claude-plugin')
      mkdirSync(v5Dir, { recursive: true })
      writeFileSync(path.join(v5Dir, 'plugin.json'), '{}')

      // No v5 commands registered → still v4.x
      const result = detectV4Installation(tmpDir)
      expect(result.isV4).toBe(true)
    })

    it('returns isV4: false when no v4 markers exist', () => {
      // Only v5 stuff
      const v5Dir = path.join(tmpDir, 'v5', 'plugins', 'pm-os-base', '.claude-plugin')
      mkdirSync(v5Dir, { recursive: true })
      writeFileSync(path.join(v5Dir, 'plugin.json'), '{}')

      const result = detectV4Installation(tmpDir)
      expect(result.isV4).toBe(false)
    })
  })
})
