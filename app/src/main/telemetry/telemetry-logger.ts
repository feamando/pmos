import { app } from 'electron'
import * as os from 'os'
import * as fs from 'fs'
import { logInfo, getLogPath, getRecentLogs } from '../installer/logger'

export type TelemetryEventType = 'SESSION_START' | 'MACHINE' | 'PMOS_VERSION' | 'CLICK' | 'USER_ERROR' | 'OUTPUT_ERROR'

export function logTelemetryEvent(eventType: TelemetryEventType, data: string): void {
  logInfo('telemetry', `[${eventType}] ${data}`)
}

export function logSessionStart(appVersion: string, electronVersion: string): void {
  logTelemetryEvent('SESSION_START', `version=${appVersion} electron=${electronVersion}`)
}

export function logMachineInfo(): void {
  logTelemetryEvent('MACHINE', `platform=${process.platform} arch=${process.arch} release=${os.release()}`)
}

export function logPmosVersion(pmosPath: string): void {
  logTelemetryEvent('PMOS_VERSION', `path=${pmosPath}`)
}

export function logClick(target: string): void {
  logTelemetryEvent('CLICK', target)
}

export function logUserError(context: string, error: string): void {
  logTelemetryEvent('USER_ERROR', `${context}: ${error}`)
}

export function logOutputError(handler: string, error: string): void {
  logTelemetryEvent('OUTPUT_ERROR', `${handler} ${error}`)
}

export function cleanupOldTelemetry(): void {
  const filePath = getLogPath('telemetry')
  try {
    if (!fs.existsSync(filePath)) return
    const content = fs.readFileSync(filePath, 'utf-8')
    if (!content.trim()) return

    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000
    const lines = content.split('\n')
    const kept: string[] = []

    for (const line of lines) {
      if (!line.trim()) continue
      const match = line.match(/^\[(\d{4}-\d{2}-\d{2}T[^\]]+)\]/)
      if (!match) {
        kept.push(line)
        continue
      }
      const ts = new Date(match[1]).getTime()
      if (isNaN(ts) || ts >= cutoff) {
        kept.push(line)
      }
    }

    fs.writeFileSync(filePath, kept.length > 0 ? kept.join('\n') + '\n' : '')
  } catch {
    // Non-critical — don't crash on cleanup failure
  }
}

export async function buildDiagnosticBundle(): Promise<string> {
  const sections: string[] = []

  // Header
  const version = app.getVersion()
  const electronVersion = process.versions.electron
  const platform = process.platform
  const arch = process.arch
  const release = os.release()
  const timestamp = new Date().toISOString()

  sections.push('--- PM-OS Diagnostic ---')
  sections.push(`App Version: ${version}`)
  sections.push(`Electron: ${electronVersion}`)
  sections.push(`Platform: ${platform} ${arch}`)
  sections.push(`OS Release: ${release}`)
  sections.push(`Generated: ${timestamp}`)
  sections.push('')

  // Recent errors from app.log
  const appLogs = getRecentLogs('app', 200)
  const errorLines = appLogs
    .split('\n')
    .filter((line) => line.includes('[ERROR]'))
    .slice(-20)

  sections.push('--- Recent Errors ---')
  if (errorLines.length > 0) {
    sections.push(errorLines.join('\n'))
  } else {
    sections.push('(none)')
  }
  sections.push('')

  // Recent telemetry
  const telemetryLogs = getRecentLogs('telemetry', 50)
  sections.push('--- Telemetry ---')
  if (telemetryLogs.trim()) {
    sections.push(telemetryLogs)
  } else {
    sections.push('(none)')
  }
  sections.push('')

  // App log tail
  const appLogTail = getRecentLogs('app', 30)
  sections.push('--- App Log (tail) ---')
  if (appLogTail.trim()) {
    sections.push(appLogTail)
  } else {
    sections.push('(none)')
  }

  return sections.join('\n')
}
