import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('child_process', () => ({
  execFile: vi.fn((cmd: any, args: any, opts: any, cb: any) => {
    const callback = typeof opts === 'function' ? opts : cb
    callback(null, 'OK', '')
    return {} as any
  }),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))

import { runPostSetup } from '../../../src/main/installer/post-setup'

describe('post-setup', () => {
  let testDir: string

  beforeEach(() => {
    vi.clearAllMocks()
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'postsetup-test-'))

    // Create directory structure
    fs.mkdirSync(path.join(testDir, 'common', '.claude', 'commands'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'common', 'tools'), { recursive: true })
    fs.mkdirSync(path.join(testDir, '.claude'), { recursive: true })
    fs.mkdirSync(path.join(testDir, '.venv', 'bin'), { recursive: true })
    fs.writeFileSync(path.join(testDir, '.venv', 'bin', 'python3'), '')

    // Create .mcp.json
    fs.writeFileSync(path.join(testDir, '.mcp.json'), JSON.stringify({
      mcpServers: { brain: { args: ['common/tools/brain/server.py'] } },
    }))
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  it('completes post-setup successfully', async () => {
    const result = await runPostSetup(testDir)
    expect(result.success).toBe(true)
  })

  it('creates sync manifest in commands directory', async () => {
    await runPostSetup(testDir)
    const manifestPath = path.join(testDir, 'common', '.claude', 'commands', '.sync-manifest.json')
    expect(fs.existsSync(manifestPath)).toBe(true)

    const content = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'))
    expect(content).toHaveProperty('synced')
  })

  it('creates settings.local.json skeleton', async () => {
    await runPostSetup(testDir)
    const settingsPath = path.join(testDir, '.claude', 'settings.local.json')
    expect(fs.existsSync(settingsPath)).toBe(true)
  })

  it('does not overwrite existing sync manifest', async () => {
    const manifestPath = path.join(testDir, 'common', '.claude', 'commands', '.sync-manifest.json')
    fs.writeFileSync(manifestPath, '{"existing":true}')

    await runPostSetup(testDir)

    const content = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'))
    expect(content).toEqual({ existing: true })
  })
})
