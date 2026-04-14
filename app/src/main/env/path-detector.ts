import fs from 'fs'
import path from 'path'
import os from 'os'

const CANDIDATE_PATHS = [
  'pm-os/user/.env',
  '.pm-os/user/.env',
]

export async function detectPmosPath(): Promise<string[]> {
  const home = os.homedir()
  const found: string[] = []

  for (const candidate of CANDIDATE_PATHS) {
    const fullPath = path.join(home, candidate)
    if (fs.existsSync(fullPath)) {
      found.push(fullPath)
    }
  }

  return found
}

export async function validateEnvPath(envPath: string): Promise<boolean> {
  try {
    if (!fs.existsSync(envPath)) return false
    const stat = fs.statSync(envPath)
    return stat.isFile()
  } catch {
    return false
  }
}
