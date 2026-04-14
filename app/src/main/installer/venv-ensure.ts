import { execFile } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import { logInfo, logOk, logError } from './logger'

function execAsync(cmd: string, args: string[], timeout = 300000): Promise<{ stdout: string; stderr: string; code: number }> {
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

/**
 * Ensures a working Python venv with critical dependencies exists at pmosPath/.venv.
 * Called on startup for existing PM-OS installations that may not have been set up
 * via the app installer (e.g. git clone users).
 *
 * This is fire-and-forget — failures are logged but don't block the app.
 */
export async function ensureVenv(pmosPath: string): Promise<void> {
  const venvPath = path.join(pmosPath, '.venv')
  const venvPython = path.join(venvPath, 'bin', 'python3')
  const venvPip = path.join(venvPath, 'bin', 'pip')

  // 1. Check if venv exists and has working Python
  if (fs.existsSync(venvPython)) {
    // Quick health check: can it import yaml?
    const check = await execAsync(venvPython, ['-c', 'import yaml; print("ok")'], 10000)
    if (check.code === 0) {
      logInfo('venv', 'Venv healthy — yaml importable')
      return
    }
    logInfo('venv', `Venv exists but yaml missing — will install deps`)
  } else {
    // Create venv
    logInfo('venv', `Creating venv at ${venvPath}`)
    const create = await execAsync('python3', ['-m', 'venv', venvPath])
    if (create.code !== 0) {
      logError('venv', `Failed to create venv: ${create.stderr.slice(0, 200)}`)
      return
    }
    logOk('venv', 'Venv created')
  }

  // 2. Install critical packages (PyYAML is the minimum needed for brain tools)
  if (!fs.existsSync(venvPip)) {
    logError('venv', 'pip not found in venv')
    return
  }

  // Try bundled requirements.txt first, fall back to critical packages only
  const bundleReqs = path.join(process.resourcesPath || '', 'bundle', 'data', 'requirements.txt')
  const devBundleReqs = path.join(__dirname, '../../bundle/data/requirements.txt')
  const reqsPath = fs.existsSync(bundleReqs) ? bundleReqs : fs.existsSync(devBundleReqs) ? devBundleReqs : null

  if (reqsPath) {
    logInfo('venv', `Installing from ${reqsPath}`)
    const install = await execAsync(venvPip, ['install', '-r', reqsPath])
    if (install.code === 0) {
      logOk('venv', 'All packages installed from requirements.txt')
      return
    }
    logError('venv', `Full install failed: ${install.stderr.slice(0, 200)} — falling back to critical packages`)
  }

  // Fallback: install just the critical packages
  logInfo('venv', 'Installing critical packages (pyyaml, python-dotenv, requests)')
  const install = await execAsync(venvPip, ['install', 'pyyaml', 'python-dotenv', 'requests'])
  if (install.code === 0) {
    logOk('venv', 'Critical packages installed')
  } else {
    logError('venv', `Critical package install failed: ${install.stderr.slice(0, 200)}`)
  }

  // 3. Install pm_os package if pyproject.toml exists (needed for google_auth etc.)
  const pyprojectPath = path.join(pmosPath, 'common', 'package', 'pyproject.toml')
  if (fs.existsSync(pyprojectPath) && fs.existsSync(venvPip)) {
    const pkgDir = path.join(pmosPath, 'common', 'package')
    logInfo('venv', 'Installing pm_os package from local source')
    const pkgInstall = await execAsync(venvPip, ['install', '-e', pkgDir])
    if (pkgInstall.code === 0) {
      logOk('venv', 'pm_os package installed')
    } else {
      logInfo('venv', `pm_os package install failed (non-critical): ${pkgInstall.stderr.slice(0, 200)}`)
    }
  }
}
