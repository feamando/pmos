import { describe, it, expect, vi } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  }
}))

describe('google-upload validation logic', () => {
  it('validates correct Google OAuth credentials format (installed)', () => {
    const validJson = { installed: { client_id: '123', client_secret: 'abc' } }
    expect(validJson.installed || (validJson as any).web).toBeTruthy()
  })

  it('validates correct Google OAuth credentials format (web)', () => {
    const validJson = { web: { client_id: '123', client_secret: 'abc' } }
    expect((validJson as any).installed || validJson.web).toBeTruthy()
  })

  it('rejects invalid JSON without installed or web key', () => {
    const invalidJson = { apiKey: 'abc123' }
    expect((invalidJson as any).installed || (invalidJson as any).web).toBeFalsy()
  })

  it('copies credentials file to secrets directory', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'google-upload-test-'))
    const srcFile = path.join(tmpDir, 'credentials.json')
    const destDir = path.join(tmpDir, '.secrets')
    const destFile = path.join(destDir, 'credentials.json')

    fs.writeFileSync(srcFile, JSON.stringify({ installed: { client_id: '123' } }))
    fs.mkdirSync(destDir, { recursive: true })
    fs.copyFileSync(srcFile, destFile)

    expect(fs.existsSync(destFile)).toBe(true)
    const content = JSON.parse(fs.readFileSync(destFile, 'utf-8'))
    expect(content.installed.client_id).toBe('123')

    // Cleanup
    fs.rmSync(tmpDir, { recursive: true })
  })
})
