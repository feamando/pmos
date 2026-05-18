import { execFile } from 'child_process'
import { existsSync } from 'fs'
import { join } from 'path'
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

/**
 * Find the git-enabled directory to pull from.
 * PM-OS may be a single git repo (git clone of hf-pm-os) or a multi-repo
 * setup where common/, user/, etc. are separate git repos.
 */
function findGitRoot(pmosPath: string): string | null {
  // 1. PM-OS root is a git repo (standard hf-pm-os clone)
  if (existsSync(join(pmosPath, '.git'))) {
    return pmosPath
  }
  // 2. common/ is a git repo (multi-repo / developer setup)
  const commonPath = join(pmosPath, 'common')
  if (existsSync(join(commonPath, '.git'))) {
    return commonPath
  }
  return null
}

export async function pullPmosRepo(pmosPath: string): Promise<GitPullResult> {
  if (!pmosPath) {
    return { success: false, message: 'PM-OS path not configured' }
  }

  const gitRoot = findGitRoot(pmosPath)
  if (!gitRoot) {
    return {
      success: false,
      message: `No git repository found at ${pmosPath} or ${join(pmosPath, 'common')}. Re-install PM-OS via git clone.`,
    }
  }

  logInfo('updater', `Running git pull in ${gitRoot}`)

  try {
    // Stash any local changes first
    const stashOutput = await runGit(['stash'], gitRoot)
    const didStash = !stashOutput.includes('No local changes')

    // Pull latest — detect default branch
    let branch = 'master'
    try {
      const remoteBranch = await runGit(['symbolic-ref', 'refs/remotes/origin/HEAD', '--short'], gitRoot)
      branch = remoteBranch.replace('origin/', '')
    } catch {
      // fallback to master
    }

    const pullOutput = await runGit(['pull', 'origin', branch], gitRoot)
    logInfo('updater', `Git pull result: ${pullOutput}`)

    // Get the short hash
    const hash = await runGit(['rev-parse', '--short', 'HEAD'], gitRoot)

    // Pop stash if we stashed
    if (didStash) {
      try {
        await runGit(['stash', 'pop'], gitRoot)
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
