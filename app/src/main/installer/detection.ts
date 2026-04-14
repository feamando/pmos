import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'
import { isDevMode, getDevPmosPath } from './dev-mode'
import { getInstallConfig } from './config-store'
import { logInfo } from './logger'

export interface DetectionResult {
  found: boolean
  path: string | null
  valid: boolean
  missing: string[]
}

const REQUIRED_PATHS = [
  'common',
  'user',
  'user/.env',
]

const OPTIONAL_MARKERS = [
  '.pm-os-root',
  'common/tools',
  'common/.claude/commands',
  'CLAUDE.md',
]

function validateInstallation(basePath: string): DetectionResult {
  const missing: string[] = []

  for (const rel of REQUIRED_PATHS) {
    const full = path.join(basePath, rel)
    if (!fs.existsSync(full)) missing.push(rel)
  }

  const found = missing.length < REQUIRED_PATHS.length // at least something exists
  const valid = missing.length === 0

  return { found, path: basePath, valid, missing }
}

export function detectPmosInstallation(): DetectionResult {
  // 1. Dev mode: ONLY check the dev temp dir — ignore real installations
  if (isDevMode()) {
    const devPath = getDevPmosPath()
    logInfo('installer', `Dev mode detection: checking ${devPath}`)
    const result = validateInstallation(devPath)
    if (result.found) return result
    logInfo('installer', 'Dev mode: no dev installation found — will trigger onboarding')
    return { found: false, path: null, valid: false, missing: REQUIRED_PATHS }
  }

  // 2. Check stored path from config (skip temp/dev paths in production)
  const config = getInstallConfig()
  if (config.pmosPath) {
    const storedPath = config.pmosPath
    const isTempPath = storedPath.includes('/T/') || storedPath.includes('/tmp/') || storedPath.includes('pmos-dev')
    if (isTempPath) {
      logInfo('installer', `Ignoring stored temp/dev path: ${storedPath}`)
    } else {
      const result = validateInstallation(storedPath)
      if (result.valid) {
        logInfo('installer', `Stored path detection: ${storedPath} (valid=${result.valid})`)
        return result
      }
      logInfo('installer', `Stored path invalid: ${storedPath} (missing: ${result.missing.join(', ')})`)
    }
  }

  // 3. Check standard locations
  const candidates = [
    path.join(os.homedir(), 'pm-os'),
    path.join(os.homedir(), '.pm-os'),
  ]

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      const result = validateInstallation(candidate)
      if (result.found) {
        logInfo('installer', `Standard path detection: ${candidate} (valid=${result.valid})`)
        return result
      }
    }
  }

  logInfo('installer', 'No PM-OS installation detected')
  return { found: false, path: null, valid: false, missing: REQUIRED_PATHS }
}

export function validateCustomPath(customPath: string): DetectionResult {
  if (!fs.existsSync(customPath)) {
    return { found: false, path: customPath, valid: false, missing: ['(path does not exist)'] }
  }
  return validateInstallation(customPath)
}
