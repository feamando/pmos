import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import { logInfo, logWarn } from './logger'

const DEV_DIR_NAME = 'pmos-dev'
const DEV_LOG_DIR_NAME = 'pmos-dev-logs'

export function isDevMode(): boolean {
  return process.env.PMOS_DEV_MODE === 'true'
}

export function getDevPmosPath(): string {
  return path.join(os.tmpdir(), DEV_DIR_NAME)
}

export function getDevLogPath(): string {
  return path.join(os.tmpdir(), DEV_LOG_DIR_NAME)
}

export function ensureDevDirs(): void {
  if (!isDevMode()) return
  const devPath = getDevPmosPath()
  fs.mkdirSync(devPath, { recursive: true })
  logInfo('installer', `Dev mode active — install target: ${devPath}`)
}

export function cleanupDevInstall(): boolean {
  const devPath = getDevPmosPath()
  try {
    if (fs.existsSync(devPath)) {
      fs.rmSync(devPath, { recursive: true, force: true })
      logInfo('installer', `Dev mode cleanup: removed ${devPath}`)
      return true
    }
    return false
  } catch (err: any) {
    logWarn('installer', `Dev mode cleanup failed: ${err.message}`)
    return false
  }
}

export function getTargetPmosPath(): string {
  if (isDevMode()) return getDevPmosPath()
  return path.join(os.homedir(), 'pm-os')
}
