import { execFile } from 'child_process'
import { logInfo, logError } from '../installer/logger'

export interface GitPullResult {
  success: boolean
  message: string
  updatedFiles?: string[]
}

function runGit(args: string[], cwd: string, timeout = 60000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, timeout }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(stderr?.trim() || err.message))
      } else {
        resolve(stdout.trim())
      }
    })
  })
}

export async function pullPmosRepo(pmosPath: string): Promise<GitPullResult> {
  if (!pmosPath) {
    return { success: false, message: 'PM-OS path not configured' }
  }

  logInfo('updater', `Running git pull in ${pmosPath}`)

  try {
    // Stash any local changes first
    const stashOutput = await runGit(['stash'], pmosPath)
    const didStash = !stashOutput.includes('No local changes')

    // Pull latest
    // feamando/pm-os uses 'main' as default branch
    const pullOutput = await runGit(['pull', 'origin', 'main'], pmosPath)
    logInfo('updater', `Git pull result: ${pullOutput}`)

    // Get the short hash
    const hash = await runGit(['rev-parse', '--short', 'HEAD'], pmosPath)

    // Pop stash if we stashed
    if (didStash) {
      try {
        await runGit(['stash', 'pop'], pmosPath)
      } catch (stashErr: any) {
        logError('updater', `Git stash pop failed: ${stashErr.message}`)
      }
    }

    // Parse updated files from pull output
    const updatedFiles = pullOutput
      .split('\n')
      .filter((line) => line.includes('|') || line.includes('=>'))
      .map((line) => line.trim().split(/\s+/)[0])
      .filter(Boolean)

    return {
      success: true,
      message: `Updated to ${hash}`,
      updatedFiles,
    }
  } catch (err: any) {
    logError('updater', `Git pull failed: ${err.message}`)
    return { success: false, message: err.message }
  }
}
