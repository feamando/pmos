import { execFile } from 'child_process'
import { existsSync } from 'fs'
import path from 'path'
import type { SyncStatus, SyncConfig } from '../../shared/types'

const DEFAULT_CONFIG: SyncConfig = {
  enabled: true,
  gatherIntervalMinutes: 30,
  synthesizeIntervalMinutes: 120,
  enableSynthesis: true,
}

function getPythonBin(pmosPath: string): string {
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  return existsSync(venvPython) ? venvPython : 'python3'
}

export function startBackgroundSync(
  pmosPath: string,
  config: SyncConfig = DEFAULT_CONFIG,
  onUpdate: (status: SyncStatus) => void,
): () => void {
  let gatherTimer: ReturnType<typeof setInterval> | null = null
  let synthesizeTimer: ReturnType<typeof setInterval> | null = null
  let synthesizeDelay: ReturnType<typeof setTimeout> | null = null
  const status: SyncStatus = {
    lastRun: null,
    lastSuccess: false,
    lastMessage: 'Not started',
    running: false,
    nextRun: null,
  }

  const pythonBin = getPythonBin(pmosPath)
  const pipelineScript = path.join(pmosPath, 'common', 'tools', 'pipeline', 'pipeline_executor.py')
  const pipelinesDir = path.join(pmosPath, 'common', 'pipelines')
  const pipelineCwd = path.join(pmosPath, 'common', 'tools', 'pipeline')

  // Verify pipeline executor exists
  if (!existsSync(pipelineScript)) {
    status.lastMessage = 'Pipeline executor not found'
    onUpdate(status)
    return () => {}
  }

  function runPipeline(yamlFile: string): Promise<{ success: boolean; message: string }> {
    return new Promise((resolve) => {
      const yamlPath = path.join(pipelinesDir, yamlFile)
      if (!existsSync(yamlPath)) {
        resolve({ success: false, message: `Pipeline not found: ${yamlFile}` })
        return
      }

      status.running = true
      onUpdate(status)

      // Build env with PM_OS_ROOT and source user/.env
      const env = {
        ...process.env,
        PM_OS_ROOT: pmosPath,
        PM_OS_COMMON: path.join(pmosPath, 'common'),
        PM_OS_USER: path.join(pmosPath, 'user'),
      }

      execFile(pythonBin, [
        pipelineScript,
        '--run', yamlPath,
        '--var', 'quiet=true',
      ], {
        timeout: 600_000, // 10 min max
        env,
        cwd: pipelineCwd,
      }, (err, stdout, stderr) => {
        status.running = false
        status.lastRun = Date.now()

        if (err) {
          status.lastSuccess = false
          const errMsg = err.message || stderr || 'Unknown error'
          status.lastMessage = errMsg.slice(0, 200)
        } else {
          status.lastSuccess = true
          const lines = stdout.trim().split('\n')
          status.lastMessage = lines[lines.length - 1] || 'Sync complete'
        }

        onUpdate(status)
        resolve({ success: status.lastSuccess, message: status.lastMessage })
      })
    })
  }

  async function gatherPoll() {
    if (status.running) return // Skip if previous run still active
    await runPipeline('background-sync.yaml')
    status.nextRun = Date.now() + config.gatherIntervalMinutes * 60_000
    onUpdate(status)
  }

  async function synthesizePoll() {
    if (!config.enableSynthesis) return
    if (status.running) return
    await runPipeline('background-synthesize.yaml')
  }

  // Start gathering
  if (config.enabled) {
    // Run gather immediately
    gatherPoll()
    gatherTimer = setInterval(gatherPoll, config.gatherIntervalMinutes * 60_000)

    // Delay synthesis by 2 minutes to let gather complete first
    if (config.enableSynthesis) {
      synthesizeDelay = setTimeout(() => {
        synthesizePoll()
        synthesizeTimer = setInterval(synthesizePoll, config.synthesizeIntervalMinutes * 60_000)
      }, 120_000)
    }
  }

  // Return stop function
  return () => {
    if (gatherTimer) { clearInterval(gatherTimer); gatherTimer = null }
    if (synthesizeTimer) { clearInterval(synthesizeTimer); synthesizeTimer = null }
    if (synthesizeDelay) { clearTimeout(synthesizeDelay); synthesizeDelay = null }
  }
}

/**
 * Run a one-shot background sync (triggered by "Sync Now" button).
 */
export function triggerImmediateSync(
  pmosPath: string,
  onUpdate: (status: SyncStatus) => void,
): Promise<{ success: boolean; message: string }> {
  const pythonBin = getPythonBin(pmosPath)
  const pipelineScript = path.join(pmosPath, 'common', 'tools', 'pipeline', 'pipeline_executor.py')
  const pipelinesDir = path.join(pmosPath, 'common', 'pipelines')
  const pipelineCwd = path.join(pmosPath, 'common', 'tools', 'pipeline')

  return new Promise((resolve) => {
    const yamlPath = path.join(pipelinesDir, 'background-sync.yaml')
    if (!existsSync(yamlPath)) {
      resolve({ success: false, message: 'background-sync.yaml not found' })
      return
    }

    onUpdate({
      lastRun: null,
      lastSuccess: false,
      lastMessage: 'Sync triggered manually',
      running: true,
      nextRun: null,
    })

    execFile(pythonBin, [
      pipelineScript,
      '--run', yamlPath,
      '--var', 'quiet=true',
    ], {
      timeout: 600_000,
      env: {
        ...process.env,
        PM_OS_ROOT: pmosPath,
        PM_OS_COMMON: path.join(pmosPath, 'common'),
        PM_OS_USER: path.join(pmosPath, 'user'),
      },
      cwd: pipelineCwd,
    }, (err, stdout) => {
      const now = Date.now()
      if (err) {
        const status: SyncStatus = {
          lastRun: now, lastSuccess: false,
          lastMessage: err.message.slice(0, 200),
          running: false, nextRun: null,
        }
        onUpdate(status)
        resolve({ success: false, message: status.lastMessage })
      } else {
        const lines = stdout.trim().split('\n')
        const msg = lines[lines.length - 1] || 'Sync complete'
        const status: SyncStatus = {
          lastRun: now, lastSuccess: true,
          lastMessage: msg, running: false, nextRun: null,
        }
        onUpdate(status)
        resolve({ success: true, message: msg })
      }
    })
  })
}
