import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))

import { distributePmos } from '../../../src/main/installer/distributor'

describe('distributor', () => {
  let testDir: string
  let bundlePath: string
  let targetPath: string

  beforeEach(() => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dist-test-'))
    bundlePath = path.join(testDir, 'bundle')
    targetPath = path.join(testDir, 'target')

    // Create bundle/common/ with some files
    const commonDir = path.join(bundlePath, 'common')
    fs.mkdirSync(path.join(commonDir, 'tools', 'brain'), { recursive: true })
    fs.mkdirSync(path.join(commonDir, '.claude', 'commands'), { recursive: true })
    fs.mkdirSync(path.join(commonDir, 'pipelines'), { recursive: true })

    fs.writeFileSync(path.join(commonDir, 'tools', 'brain', 'brain_index.py'), '#!/usr/bin/env python3\nprint("brain")')
    fs.writeFileSync(path.join(commonDir, '.claude', 'commands', 'boot.md'), '# Boot\n')
    fs.writeFileSync(path.join(commonDir, 'pipelines', 'boot.yaml'), 'steps: []\n')
    fs.writeFileSync(path.join(commonDir, 'AGENT.md'), '# Agent\n')

    // Create target directory
    fs.mkdirSync(path.join(targetPath, 'common'), { recursive: true })
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  it('copies all files from bundle/common/ to target/common/', async () => {
    const result = await distributePmos(bundlePath, targetPath)

    expect(result.success).toBe(true)
    expect(fs.existsSync(path.join(targetPath, 'common', 'tools', 'brain', 'brain_index.py'))).toBe(true)
    expect(fs.existsSync(path.join(targetPath, 'common', '.claude', 'commands', 'boot.md'))).toBe(true)
    expect(fs.existsSync(path.join(targetPath, 'common', 'pipelines', 'boot.yaml'))).toBe(true)
    expect(fs.existsSync(path.join(targetPath, 'common', 'AGENT.md'))).toBe(true)
  })

  it('sets executable permissions on .py files', async () => {
    await distributePmos(bundlePath, targetPath)

    const stats = fs.statSync(path.join(targetPath, 'common', 'tools', 'brain', 'brain_index.py'))
    expect(stats.mode & 0o755).toBe(0o755)
  })

  it('reports progress during copy', async () => {
    const progressCalls: [number, number][] = []
    await distributePmos(bundlePath, targetPath, (copied, total) => {
      progressCalls.push([copied, total])
    })

    expect(progressCalls.length).toBeGreaterThan(0)
    const last = progressCalls[progressCalls.length - 1]
    expect(last[0]).toBeGreaterThan(0)
  })

  it('fails when bundle/common/ does not exist', async () => {
    const emptyBundle = path.join(testDir, 'empty')
    fs.mkdirSync(emptyBundle, { recursive: true })

    const result = await distributePmos(emptyBundle, targetPath)
    expect(result.success).toBe(false)
    expect(result.message).toContain('not found')
  })

  it('skips files when target is newer', async () => {
    // First distribution
    await distributePmos(bundlePath, targetPath)

    // Modify target file to be "newer"
    const targetFile = path.join(targetPath, 'common', 'AGENT.md')
    fs.writeFileSync(targetFile, '# Modified Agent\n')
    // Touch to make it clearly newer
    const futureTime = Date.now() / 1000 + 1000
    fs.utimesSync(targetFile, futureTime, futureTime)

    // Second distribution
    await distributePmos(bundlePath, targetPath)

    const content = fs.readFileSync(targetFile, 'utf-8')
    expect(content).toBe('# Modified Agent\n')
  })
})
