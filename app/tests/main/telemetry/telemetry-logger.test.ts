import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('electron', () => ({
  app: {
    getPath: (name: string) => {
      if (name === 'logs') return path.join(os.tmpdir(), 'pmos-telemetry-test')
      return os.tmpdir()
    },
    getVersion: () => '0.10.0-20260331',
  },
}))

import {
  logTelemetryEvent,
  logSessionStart,
  logMachineInfo,
  logClick,
  logUserError,
  logOutputError,
  cleanupOldTelemetry,
  buildDiagnosticBundle,
} from '../../../src/main/telemetry/telemetry-logger'
import { logInfo, getLogPath } from '../../../src/main/installer/logger'

describe('telemetry-logger', () => {
  let testLogDir: string

  beforeEach(() => {
    testLogDir = path.join(os.tmpdir(), 'pmos-telemetry-test', 'PM-OS')
    fs.mkdirSync(testLogDir, { recursive: true })
  })

  afterEach(() => {
    fs.rmSync(path.join(os.tmpdir(), 'pmos-telemetry-test'), { recursive: true, force: true })
  })

  // --- Task 4.1: Telemetry event logging ---

  describe('event logging', () => {
    it('logTelemetryEvent writes formatted line to telemetry.log', () => {
      logTelemetryEvent('CLICK', 'test_target')
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[CLICK] test_target')
      expect(content).toContain('[telemetry]')
      expect(content).toMatch(/\[\d{4}-\d{2}-\d{2}T/)
    })

    it('logSessionStart writes SESSION_START with version info', () => {
      logSessionStart('0.10.0', '41.1.0')
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[SESSION_START] version=0.10.0 electron=41.1.0')
    })

    it('logMachineInfo writes MACHINE with platform/arch/release', () => {
      logMachineInfo()
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[MACHINE]')
      expect(content).toContain(`platform=${process.platform}`)
      expect(content).toContain(`arch=${process.arch}`)
      expect(content).toContain('release=')
    })

    it('logClick writes CLICK with target', () => {
      logClick('page=brain')
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[CLICK] page=brain')
    })

    it('logUserError writes USER_ERROR with context and error', () => {
      logUserError('get-brain-health', 'Brain folder not found')
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[USER_ERROR] get-brain-health: Brain folder not found')
    })

    it('logOutputError writes OUTPUT_ERROR with handler and error', () => {
      logOutputError('ipc:save-connection', 'EPIPE')
      const content = fs.readFileSync(path.join(testLogDir, 'telemetry.log'), 'utf-8')
      expect(content).toContain('[OUTPUT_ERROR] ipc:save-connection EPIPE')
    })
  })

  // --- Task 4.2: 7-day auto-cleanup ---

  describe('cleanupOldTelemetry', () => {
    it('removes lines older than 7 days', () => {
      const telemetryPath = getLogPath('telemetry')
      const oldDate = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString()
      const recentDate = new Date().toISOString()
      const content = [
        `[${oldDate}] [INFO]  [telemetry] [CLICK] old_event`,
        `[${recentDate}] [INFO]  [telemetry] [CLICK] recent_event`,
      ].join('\n') + '\n'
      fs.writeFileSync(telemetryPath, content)

      cleanupOldTelemetry()

      const result = fs.readFileSync(telemetryPath, 'utf-8')
      expect(result).not.toContain('old_event')
      expect(result).toContain('recent_event')
    })

    it('preserves lines within 7 days', () => {
      const telemetryPath = getLogPath('telemetry')
      const recentDate = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
      const content = `[${recentDate}] [INFO]  [telemetry] [CLICK] keep_me\n`
      fs.writeFileSync(telemetryPath, content)

      cleanupOldTelemetry()

      const result = fs.readFileSync(telemetryPath, 'utf-8')
      expect(result).toContain('keep_me')
    })

    it('handles empty file without crash', () => {
      const telemetryPath = getLogPath('telemetry')
      fs.writeFileSync(telemetryPath, '')
      expect(() => cleanupOldTelemetry()).not.toThrow()
    })

    it('handles missing file without crash', () => {
      expect(() => cleanupOldTelemetry()).not.toThrow()
    })

    it('preserves lines with unparseable timestamps', () => {
      const telemetryPath = getLogPath('telemetry')
      const content = 'some weird line without timestamp\n'
      fs.writeFileSync(telemetryPath, content)

      cleanupOldTelemetry()

      const result = fs.readFileSync(telemetryPath, 'utf-8')
      expect(result).toContain('some weird line without timestamp')
    })
  })

  // --- Task 4.3: Diagnostic bundle builder ---

  describe('buildDiagnosticBundle', () => {
    it('contains header with version and platform', async () => {
      const bundle = await buildDiagnosticBundle()
      expect(bundle).toContain('--- PM-OS Diagnostic ---')
      expect(bundle).toContain('App Version: 0.10.0-20260331')
      expect(bundle).toContain(`Platform: ${process.platform} ${process.arch}`)
    })

    it('contains Recent Errors section', async () => {
      // Write an error to app.log
      logInfo('app', 'Normal line')
      const appLogPath = getLogPath('app')
      fs.appendFileSync(appLogPath, `[${new Date().toISOString()}] [ERROR] [app] Something broke\n`)

      const bundle = await buildDiagnosticBundle()
      expect(bundle).toContain('--- Recent Errors ---')
      expect(bundle).toContain('Something broke')
    })

    it('contains Telemetry section', async () => {
      logClick('page=home')
      const bundle = await buildDiagnosticBundle()
      expect(bundle).toContain('--- Telemetry ---')
      expect(bundle).toContain('[CLICK] page=home')
    })

    it('contains App Log tail section', async () => {
      logInfo('app', 'Tail line test')
      const bundle = await buildDiagnosticBundle()
      expect(bundle).toContain('--- App Log (tail) ---')
      expect(bundle).toContain('Tail line test')
    })
  })
})
