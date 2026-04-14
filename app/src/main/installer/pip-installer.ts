import { execFile } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'
import { logInfo, logError } from './logger'
import type { StepResult } from './dep-installer'

function execAsync(cmd: string, args: string[], opts: { timeout?: number; env?: Record<string, string> } = {}): Promise<{ stdout: string; stderr: string; code: number }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: opts.timeout || 300000, env: { ...process.env, ...opts.env } }, (err, stdout, stderr) => {
      resolve({
        stdout: stdout?.toString() || '',
        stderr: stderr?.toString() || '',
        code: err ? (err as any).code || 1 : 0,
      })
    })
  })
}

export async function createVenv(pmosPath: string): Promise<StepResult> {
  const start = Date.now()
  const venvPath = path.join(pmosPath, '.venv')

  if (fs.existsSync(venvPath)) {
    logInfo('installer', `Venv already exists at ${venvPath}`)
    return { success: true, message: 'Virtual environment already exists', duration: 0 }
  }

  logInfo('installer', `Creating venv at ${venvPath}`)
  const result = await execAsync('python3', ['-m', 'venv', venvPath])
  const duration = (Date.now() - start) / 1000

  if (result.code === 0) {
    logInfo('installer', `Venv created (${duration.toFixed(1)}s)`)
    return { success: true, message: 'Virtual environment created', duration }
  }

  logError('installer', `Venv creation failed: ${result.stderr}`)
  return { success: false, message: `Venv creation failed: ${result.stderr.slice(0, 200)}`, duration }
}

export async function installPipPackages(
  pmosPath: string,
  requirementsPath: string,
  onProgress?: (installed: number, total: number) => void,
): Promise<StepResult> {
  const start = Date.now()

  if (!fs.existsSync(requirementsPath)) {
    return { success: false, message: `requirements.txt not found at ${requirementsPath}`, duration: 0 }
  }

  const pipPath = path.join(pmosPath, '.venv', 'bin', 'pip')
  if (!fs.existsSync(pipPath)) {
    return { success: false, message: 'Virtual environment pip not found — run createVenv first', duration: 0 }
  }

  // Count total packages for progress
  const reqContent = fs.readFileSync(requirementsPath, 'utf-8')
  const totalPkgs = reqContent.split('\n').filter((l) => l.trim() && !l.startsWith('#')).length

  logInfo('installer', `Installing ${totalPkgs} pip packages...`)

  const result = await execAsync(pipPath, ['install', '-r', requirementsPath], { timeout: 300000 })
  const duration = (Date.now() - start) / 1000

  if (result.code === 0) {
    if (onProgress) onProgress(totalPkgs, totalPkgs)
    logInfo('installer', `Pip packages installed (${duration.toFixed(1)}s)`)
    return { success: true, message: `${totalPkgs} packages installed`, duration }
  }

  logError('installer', `Pip install failed: ${result.stderr.slice(0, 500)}`)
  return { success: false, message: `Pip install failed: ${result.stderr.slice(0, 200)}`, duration }
}

export async function verifyCriticalPackages(pmosPath: string): Promise<StepResult> {
  const start = Date.now()
  const pythonPath = path.join(pmosPath, '.venv', 'bin', 'python3')
  const packages = ['yaml', 'dotenv', 'requests', 'slack_sdk', 'anthropic']

  const importStmt = packages.map((p) => `import ${p}`).join('; ')
  const result = await execAsync(pythonPath, ['-c', importStmt])
  const duration = (Date.now() - start) / 1000

  if (result.code === 0) {
    logInfo('installer', 'Critical packages verified')
    return { success: true, message: 'All critical packages importable', duration }
  }

  logError('installer', `Package verification failed: ${result.stderr}`)
  return { success: false, message: `Missing packages: ${result.stderr.slice(0, 200)}`, duration }
}
