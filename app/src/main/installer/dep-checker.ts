import { execFile, execFileSync } from 'child_process'
import { existsSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'
import { logInfo } from './logger'

export interface DepStatus {
  python: { found: boolean; version: string | null; path: string | null }
  pip: { found: boolean; path: string | null }
  xcode: boolean
  git: boolean
}

function exec(cmd: string, args: string[], timeout = 10000): Promise<{ stdout: string; code: number }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (err, stdout) => {
      resolve({ stdout: stdout?.toString().trim() || '', code: err ? 1 : 0 })
    })
  })
}

/**
 * Resolve the user's real PATH by spawning a login shell.
 * Desktop apps (Electron) don't inherit shell profile PATH, so pyenv/asdf/conda
 * Python installations are invisible to bare execFile() calls.
 */
function getUserShellPath(): string | null {
  const shells = [process.env.SHELL || '/bin/zsh', '/bin/zsh', '/bin/bash']
  for (const shell of shells) {
    try {
      const result = execFileSync(shell, ['-lc', 'echo $PATH'], { timeout: 5000, encoding: 'utf-8' })
      const shellPath = result.trim()
      if (shellPath) {
        logInfo('installer', `Resolved user shell PATH via ${shell} (${shellPath.split(':').length} entries)`)
        return shellPath
      }
    } catch {
      // try next shell
    }
  }
  return null
}

/**
 * Build the list of candidate Python paths to check.
 * Combines hardcoded known locations, version manager shims, and
 * any additional paths discovered from the user's login shell.
 */
function buildPythonCandidates(): string[] {
  const home = homedir()
  const candidates = [
    // 1. Bare command (works if already in process PATH)
    'python3',
    // 2. Standard system locations
    '/usr/bin/python3',
    '/usr/local/bin/python3',
    // 3. Homebrew (Apple Silicon + Intel)
    '/opt/homebrew/bin/python3',
    // 4. Common version managers
    join(home, '.pyenv/shims/python3'),
    join(home, '.asdf/shims/python3'),
    // 5. Conda
    join(home, 'miniconda3/bin/python3'),
    join(home, 'anaconda3/bin/python3'),
    join(home, 'miniforge3/bin/python3'),
  ]

  // 6. Discover additional paths from user's login shell
  const shellPath = getUserShellPath()
  if (shellPath) {
    for (const dir of shellPath.split(':')) {
      const candidate = join(dir, 'python3')
      if (!candidates.includes(candidate) && existsSync(candidate)) {
        candidates.push(candidate)
      }
    }
  }

  return candidates
}

export async function checkPython(): Promise<{ found: boolean; version: string | null; path: string | null }> {
  const candidates = buildPythonCandidates()
  logInfo('installer', `Checking ${candidates.length} Python candidates`)

  for (const p of candidates) {
    const result = await exec(p, ['--version'])
    if (result.code === 0) {
      const match = result.stdout.match(/Python (\d+\.\d+\.\d+)/)
      if (match) {
        const version = match[1]
        const [major, minor] = version.split('.').map(Number)
        if (major >= 3 && minor >= 10) {
          // Resolve to absolute path
          const which = await exec('which', [p])
          const resolved = which.stdout || p
          logInfo('installer', `Python found: ${version} at ${resolved}`)
          return { found: true, version, path: resolved }
        }
      }
    }
  }
  logInfo('installer', 'Python 3.10+ not found after checking all candidates')
  return { found: false, version: null, path: null }
}

export async function checkPip(): Promise<{ found: boolean; path: string | null }> {
  // pip3 lives alongside python3 — check the same locations
  const home = homedir()
  const candidates = [
    'pip3',
    '/usr/bin/pip3',
    '/usr/local/bin/pip3',
    '/opt/homebrew/bin/pip3',
    join(home, '.pyenv/shims/pip3'),
    join(home, '.asdf/shims/pip3'),
    join(home, 'miniconda3/bin/pip3'),
    join(home, 'anaconda3/bin/pip3'),
    join(home, 'miniforge3/bin/pip3'),
  ]

  for (const p of candidates) {
    const result = await exec(p, ['--version'])
    if (result.code === 0) {
      const which = await exec('which', [p])
      const resolved = which.stdout || p
      logInfo('installer', `pip found at ${resolved}`)
      return { found: true, path: resolved }
    }
  }
  logInfo('installer', 'pip3 not found after checking all candidates')
  return { found: false, path: null }
}

export async function checkXcodeTools(): Promise<boolean> {
  const result = await exec('xcode-select', ['-p'])
  const found = result.code === 0
  logInfo('installer', `Xcode CLT: ${found ? 'found' : 'not found'}`)
  return found
}

export async function checkGit(): Promise<boolean> {
  const result = await exec('git', ['--version'])
  const found = result.code === 0
  logInfo('installer', `git: ${found ? result.stdout : 'not found'}`)
  return found
}

export async function checkAllDeps(): Promise<DepStatus> {
  const [python, pip, xcode, git] = await Promise.all([
    checkPython(),
    checkPip(),
    checkXcodeTools(),
    checkGit(),
  ])
  return { python, pip, xcode, git }
}
