import { execFile, spawn } from 'child_process'
import { logInfo, logError } from './logger'

export interface StepResult {
  success: boolean
  message: string
  duration: number
}

function execAsync(cmd: string, args: string[], timeout = 600000): Promise<{ stdout: string; stderr: string; code: number }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (err, stdout, stderr) => {
      resolve({
        stdout: stdout?.toString() || '',
        stderr: stderr?.toString() || '',
        code: err ? (err as any).code || 1 : 0,
      })
    })
  })
}

export async function installXcodeTools(): Promise<StepResult> {
  const start = Date.now()
  logInfo('installer', 'Installing Xcode Command Line Tools...')

  // Trigger the system install dialog
  const proc = spawn('xcode-select', ['--install'], { stdio: 'ignore' })
  proc.unref()

  // Poll for completion (system dialog runs async)
  const timeoutMs = 10 * 60 * 1000 // 10 minutes
  const pollInterval = 5000
  let elapsed = 0

  while (elapsed < timeoutMs) {
    await new Promise((r) => setTimeout(r, pollInterval))
    elapsed += pollInterval

    const check = await execAsync('xcode-select', ['-p'], 10000)
    if (check.code === 0) {
      const duration = (Date.now() - start) / 1000
      logInfo('installer', `Xcode CLT installed (${duration.toFixed(1)}s)`)
      return { success: true, message: 'Xcode Command Line Tools installed', duration }
    }
  }

  const duration = (Date.now() - start) / 1000
  logError('installer', 'Xcode CLT install timed out')
  return { success: false, message: 'Xcode CLT installation timed out (10min)', duration }
}

export async function installPython(): Promise<StepResult> {
  const start = Date.now()

  // Strategy A: try Homebrew
  const brewCheck = await execAsync('which', ['brew'], 5000)
  if (brewCheck.code === 0) {
    logInfo('installer', 'Installing Python via Homebrew...')
    const result = await execAsync('brew', ['install', 'python@3.12'])
    if (result.code === 0) {
      const duration = (Date.now() - start) / 1000
      logInfo('installer', `Python installed via Homebrew (${duration.toFixed(1)}s)`)
      return { success: true, message: 'Python 3.12 installed via Homebrew', duration }
    }
    logError('installer', `Homebrew Python install failed: ${result.stderr}`)
  }

  // Strategy B: python.org installer
  logInfo('installer', 'Homebrew not available, attempting python.org installer...')
  // Download and run the pkg
  const pkgUrl = 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-macos11.pkg'
  const tmpPkg = '/tmp/python-installer.pkg'

  const download = await execAsync('curl', ['-fSL', '-o', tmpPkg, pkgUrl], 120000)
  if (download.code !== 0) {
    const duration = (Date.now() - start) / 1000
    logError('installer', `Python download failed: ${download.stderr}`)
    return { success: false, message: 'Failed to download Python installer', duration }
  }

  const install = await execAsync('sudo', ['installer', '-pkg', tmpPkg, '-target', '/'], 300000)
  if (install.code === 0) {
    const duration = (Date.now() - start) / 1000
    logInfo('installer', `Python installed via python.org pkg (${duration.toFixed(1)}s)`)
    return { success: true, message: 'Python 3.12 installed via python.org', duration }
  }

  const duration = (Date.now() - start) / 1000
  logError('installer', `Python.org install failed: ${install.stderr}`)
  return { success: false, message: 'Failed to install Python', duration }
}

export async function installPip(): Promise<StepResult> {
  const start = Date.now()
  logInfo('installer', 'Ensuring pip...')
  const result = await execAsync('python3', ['-m', 'ensurepip', '--upgrade'])
  const duration = (Date.now() - start) / 1000
  if (result.code === 0) {
    logInfo('installer', `pip ensured (${duration.toFixed(1)}s)`)
    return { success: true, message: 'pip installed', duration }
  }
  logError('installer', `pip install failed: ${result.stderr}`)
  return { success: false, message: `pip install failed: ${result.stderr.slice(0, 200)}`, duration }
}
