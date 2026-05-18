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

  const trigger = await execAsync('xcode-select', ['--install'], 10000)
  if (trigger.code !== 0 && trigger.stderr.includes('already installed')) {
    const duration = (Date.now() - start) / 1000
    logInfo('installer', 'Xcode CLT already installed')
    return { success: true, message: 'Xcode Command Line Tools already installed', duration }
  }

  const proc = spawn('xcode-select', ['--install'], { stdio: 'ignore' })
  proc.unref()

  const timeoutMs = 3 * 60 * 1000
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
  return { success: false, message: 'Xcode CLT installation timed out. Please install manually: open Terminal and run "xcode-select --install"', duration }
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

  const duration = (Date.now() - start) / 1000
  logError('installer', 'Python 3.10+ not found and Homebrew not available')
  return {
    success: false,
    message: 'Python 3.10+ is required but was not found.\n\nIf you already installed Python, you may need to restart HelloAI so it can detect it.\n\nOtherwise, install from https://python.org/downloads\nor open Terminal and run: brew install python@3.12\n\nThen click Retry.',
    duration,
  }
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
