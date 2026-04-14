import { app } from 'electron'
import * as fs from 'fs'
import * as path from 'path'

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'OK'
export type LogCategory = 'installer' | 'app' | 'renderer' | 'verify' | 'telemetry'

const MAX_LOG_SIZE = 5 * 1024 * 1024 // 5MB

// Suppress EPIPE errors on stdout/stderr (async stream errors from broken pipes)
process.stdout?.on?.('error', () => {})
process.stderr?.on?.('error', () => {})

let logDir: string | null = null

function getLogDir(): string {
  if (logDir) return logDir
  logDir = path.join(app.getPath('logs'), 'PM-OS')
  fs.mkdirSync(logDir, { recursive: true })
  return logDir
}

function getLogPath(category: LogCategory): string {
  return path.join(getLogDir(), `${category}.log`)
}

function rotateIfNeeded(filePath: string): void {
  try {
    const stats = fs.statSync(filePath)
    if (stats.size > MAX_LOG_SIZE) {
      const rotated = filePath + '.1'
      if (fs.existsSync(rotated)) fs.unlinkSync(rotated)
      fs.renameSync(filePath, rotated)
    }
  } catch {
    // File doesn't exist yet — nothing to rotate
  }
}

function formatLine(level: LogLevel, category: LogCategory, message: string): string {
  const ts = new Date().toISOString()
  const pad = level.length < 4 ? ' '.repeat(5 - level.length) : ' '
  return `[${ts}] [${level}]${pad}[${category}] ${message}\n`
}

export function log(level: LogLevel, category: LogCategory, message: string): void {
  const filePath = getLogPath(category)
  rotateIfNeeded(filePath)
  const line = formatLine(level, category, message)
  fs.appendFileSync(filePath, line)

  // Console output disabled — Electron's stdout pipe can break (EPIPE).
  // All logs go to files in getLogDir().
}

export function logInfo(category: LogCategory, message: string): void {
  log('INFO', category, message)
}

export function logWarn(category: LogCategory, message: string): void {
  log('WARN', category, message)
}

export function logError(category: LogCategory, message: string): void {
  log('ERROR', category, message)
}

export function logOk(category: LogCategory, message: string): void {
  log('OK', category, message)
}

export function getRecentLogs(category: LogCategory, lines: number = 50): string {
  const filePath = getLogPath(category)
  try {
    const content = fs.readFileSync(filePath, 'utf-8')
    const allLines = content.trim().split('\n')
    return allLines.slice(-lines).join('\n')
  } catch {
    return ''
  }
}

export { getLogDir, getLogPath }
