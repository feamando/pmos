import { BrowserWindow } from 'electron'
import * as path from 'path'
import { checkAllDeps } from './dep-checker'
import { installXcodeTools, installPython, installPip } from './dep-installer'
import { createVenv, installPipPackages, verifyCriticalPackages } from './pip-installer'
import { createFolderStructure } from './scaffolder'
import { generateConfigFiles } from './config-generator'
import { distributeGoogleCredentials } from './scaffolder'
import { distributePmos } from './distributor'
import { runPostSetup } from './post-setup'
import { runVerification } from './verifier'
import { logInfo, logError, logOk } from './logger'
import { isDevMode, getTargetPmosPath } from './dev-mode'
import { setInstallConfig } from './config-store'
import { splashShowProgress, splashUpdateProgress, splashShowSuccess, splashShowError } from '../splash'
import type { InstallStep, InstallResult } from '../../shared/types'

export interface OrchestratorCallbacks {
  onProgress: (step: number, total: number, name: string, pct: number, steps: InstallStep[]) => void
  onComplete: (result: InstallResult) => void
}

function makeSteps(): InstallStep[] {
  return [
    { id: 'deps', name: 'Checking dependencies', status: 'pending', pct: 0 },
    { id: 'sys-deps', name: 'Installing system dependencies', status: 'pending', pct: 0 },
    { id: 'venv', name: 'Creating Python environment', status: 'pending', pct: 0 },
    { id: 'pip', name: 'Installing Python packages', status: 'pending', pct: 0 },
    { id: 'scaffold', name: 'Creating folder structure', status: 'pending', pct: 0 },
    { id: 'config', name: 'Generating configuration files', status: 'pending', pct: 0 },
    { id: 'distribute', name: 'Unpacking PM-OS tools', status: 'pending', pct: 0 },
    { id: 'post-setup', name: 'Configuring PM-OS', status: 'pending', pct: 0 },
    { id: 'verify', name: 'Verifying installation', status: 'pending', pct: 0 },
  ]
}

function updateStep(steps: InstallStep[], id: string, status: InstallStep['status'], pct: number = 0): void {
  const step = steps.find((s) => s.id === id)
  if (step) {
    step.status = status
    step.pct = pct
  }
}

function overallPct(steps: InstallStep[]): number {
  const done = steps.filter((s) => s.status === 'done').length
  const running = steps.filter((s) => s.status === 'running').length
  return Math.round(((done + running * 0.5) / steps.length) * 100)
}

export async function runInstallation(
  splash: BrowserWindow | null,
  callbacks?: OrchestratorCallbacks,
): Promise<InstallResult> {
  const startTime = Date.now()
  const targetPath = getTargetPmosPath()
  const steps = makeSteps()
  const errors: string[] = []

  logInfo('installer', `Starting installation to ${targetPath} (devMode=${isDevMode()})`)

  function report(stepId: string) {
    const step = steps.find((s) => s.id === stepId)
    const pct = overallPct(steps)
    if (splash) splashUpdateProgress(splash, step?.name || '', pct, steps)
    if (callbacks?.onProgress) {
      const idx = steps.findIndex((s) => s.id === stepId)
      callbacks.onProgress(idx + 1, steps.length, step?.name || '', pct, steps)
    }
  }

  if (splash) splashShowProgress(splash)

  // Step 1: Check dependencies
  updateStep(steps, 'deps', 'running')
  report('deps')
  const deps = await checkAllDeps()
  updateStep(steps, 'deps', 'done', 100)
  report('deps')

  // Step 2: Install missing system deps
  updateStep(steps, 'sys-deps', 'running')
  report('sys-deps')
  try {
    if (!deps.xcode) {
      const r = await installXcodeTools()
      if (!r.success) { errors.push(r.message); updateStep(steps, 'sys-deps', 'error'); report('sys-deps'); }
    }
    if (!deps.python.found) {
      const r = await installPython()
      if (!r.success) { errors.push(r.message); updateStep(steps, 'sys-deps', 'error'); report('sys-deps'); }
    }
    if (!deps.pip.found) {
      const r = await installPip()
      if (!r.success) { errors.push(r.message); updateStep(steps, 'sys-deps', 'error'); report('sys-deps'); }
    }
    if (steps.find((s) => s.id === 'sys-deps')?.status !== 'error') {
      updateStep(steps, 'sys-deps', 'done', 100)
    }
  } catch (err: any) {
    errors.push(err.message)
    updateStep(steps, 'sys-deps', 'error')
  }
  report('sys-deps')

  // If critical deps failed, stop
  if (errors.length > 0) {
    return finish(targetPath, errors, startTime, splash, callbacks)
  }

  // Step 3: Create venv
  updateStep(steps, 'venv', 'running')
  report('venv')
  const venvResult = await createVenv(targetPath)
  updateStep(steps, 'venv', venvResult.success ? 'done' : 'error', 100)
  if (!venvResult.success) errors.push(venvResult.message)
  report('venv')

  // Step 4: Install pip packages
  updateStep(steps, 'pip', 'running')
  report('pip')
  const bundlePath = getBundlePath()
  const reqPath = path.join(bundlePath, 'data', 'requirements.txt')
  const pipResult = await installPipPackages(targetPath, reqPath)
  updateStep(steps, 'pip', pipResult.success ? 'done' : 'error', 100)
  if (!pipResult.success) errors.push(pipResult.message)
  report('pip')

  // Step 5: Create folder structure
  updateStep(steps, 'scaffold', 'running')
  report('scaffold')
  const scaffoldResult = await createFolderStructure(targetPath)
  updateStep(steps, 'scaffold', scaffoldResult.success ? 'done' : 'error', 100)
  if (!scaffoldResult.success) errors.push(scaffoldResult.message)
  report('scaffold')

  // Step 6: Generate config files
  updateStep(steps, 'config', 'running')
  report('config')
  const configResult = await generateConfigFiles(targetPath, bundlePath)
  updateStep(steps, 'config', configResult.success ? 'done' : 'error', 100)
  if (!configResult.success) errors.push(configResult.message)
  report('config')

  // Step 7: Distribute PM-OS
  updateStep(steps, 'distribute', 'running')
  report('distribute')
  const distResult = await distributePmos(bundlePath, targetPath)
  updateStep(steps, 'distribute', distResult.success ? 'done' : 'error', 100)
  if (!distResult.success) errors.push(distResult.message)
  report('distribute')

  // Step 7.5: Distribute Google credentials
  await distributeGoogleCredentials(targetPath, bundlePath)

  // Step 8: Post-setup
  updateStep(steps, 'post-setup', 'running')
  report('post-setup')
  const postResult = await runPostSetup(targetPath)
  updateStep(steps, 'post-setup', postResult.success ? 'done' : 'error', 100)
  if (!postResult.success) errors.push(postResult.message)
  report('post-setup')

  // Step 9: Verify
  updateStep(steps, 'verify', 'running')
  report('verify')
  const verifyResult = await runVerification(targetPath)
  updateStep(steps, 'verify', verifyResult.success ? 'done' : 'error', 100)
  if (!verifyResult.success) {
    const failedChecks = verifyResult.checks.filter((c) => !c.passed)
    errors.push(...failedChecks.map((c) => `Verify failed: ${c.name} — ${c.message}`))
  }
  report('verify')

  return finish(targetPath, errors, startTime, splash, callbacks)
}

function finish(
  targetPath: string,
  errors: string[],
  startTime: number,
  splash: BrowserWindow | null,
  callbacks?: OrchestratorCallbacks,
): InstallResult {
  const duration = (Date.now() - startTime) / 1000
  const success = errors.length === 0

  if (success) {
    logOk('installer', `Installation complete (${duration.toFixed(1)}s)`)
    setInstallConfig({ pmosPath: targetPath, installComplete: true, installedAt: new Date().toISOString() })
    if (splash) splashShowSuccess(splash)
  } else {
    logError('installer', `Installation failed with ${errors.length} error(s): ${errors.join('; ')}`)
    if (splash) splashShowError(splash, errors.join('\n'))
  }

  const result: InstallResult = { success, errors, duration, pmosPath: targetPath }
  if (callbacks?.onComplete) callbacks.onComplete(result)
  return result
}

function getBundlePath(): string {
  // In dev: bundle/ dir relative to project root
  // In packaged app: extraResources/bundle/
  const devBundlePath = path.join(__dirname, '../../bundle')
  const prodBundlePath = path.join(process.resourcesPath || '', 'bundle')
  const { existsSync } = require('fs')
  return existsSync(devBundlePath) ? devBundlePath : prodBundlePath
}
