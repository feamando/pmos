import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

// Mock electron app
vi.mock('electron', () => ({
  app: {
    getPath: (name: string) => {
      if (name === 'logs') return path.join(os.tmpdir(), 'pmos-test-logs')
      return os.tmpdir()
    },
  },
}))

import { log, logInfo, logOk, logError, getRecentLogs, getLogDir } from '../../../src/main/installer/logger'

describe('logger', () => {
  let testLogDir: string

  beforeEach(() => {
    testLogDir = path.join(os.tmpdir(), 'pmos-test-logs', 'PM-OS')
    fs.mkdirSync(testLogDir, { recursive: true })
  })

  afterEach(() => {
    fs.rmSync(path.join(os.tmpdir(), 'pmos-test-logs'), { recursive: true, force: true })
  })

  it('formats log lines correctly', () => {
    logInfo('installer', 'Test message')
    const content = fs.readFileSync(path.join(testLogDir, 'installer.log'), 'utf-8')
    expect(content).toMatch(/\[\d{4}-\d{2}-\d{2}T.*\] \[INFO\]\s+\[installer\] Test message/)
  })

  it('writes different log levels', () => {
    logOk('installer', 'Step complete')
    logError('installer', 'Something broke')
    const content = fs.readFileSync(path.join(testLogDir, 'installer.log'), 'utf-8')
    expect(content).toContain('[OK]')
    expect(content).toContain('[ERROR]')
  })

  it('writes to category-specific files', () => {
    logInfo('installer', 'installer msg')
    logInfo('app', 'app msg')
    expect(fs.existsSync(path.join(testLogDir, 'installer.log'))).toBe(true)
    expect(fs.existsSync(path.join(testLogDir, 'app.log'))).toBe(true)
  })

  it('getRecentLogs returns last N lines', () => {
    for (let i = 0; i < 10; i++) {
      logInfo('verify', `Line ${i}`)
    }
    const recent = getRecentLogs('verify', 3)
    const lines = recent.trim().split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[2]).toContain('Line 9')
  })

  it('getRecentLogs returns empty string for missing file', () => {
    const result = getRecentLogs('renderer', 10)
    expect(result).toBe('')
  })
})
