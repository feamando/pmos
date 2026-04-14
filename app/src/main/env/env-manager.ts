import fs from 'fs'
import path from 'path'

interface EnvLine {
  type: 'comment' | 'blank' | 'entry'
  raw: string
  key?: string
  value?: string
}

export interface EnvFile {
  lines: EnvLine[]
  filePath: string
}

export function parseEnvContent(content: string): EnvLine[] {
  return content.split('\n').map((raw) => {
    const trimmed = raw.trim()
    if (trimmed === '') return { type: 'blank', raw }
    if (trimmed.startsWith('#')) return { type: 'comment', raw }
    const eqIndex = raw.indexOf('=')
    if (eqIndex === -1) return { type: 'comment', raw } // malformed → preserve as-is
    const key = raw.slice(0, eqIndex).trim()
    let value = raw.slice(eqIndex + 1).trim()
    // Strip surrounding quotes
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    return { type: 'entry', raw, key, value }
  })
}

export async function parseEnvFile(filePath: string): Promise<EnvFile> {
  if (!fs.existsSync(filePath)) {
    return { lines: [], filePath }
  }
  const content = fs.readFileSync(filePath, 'utf-8')
  return { lines: parseEnvContent(content), filePath }
}

export function readEnvValue(envFile: EnvFile, key: string): string | null {
  const line = envFile.lines.find((l) => l.type === 'entry' && l.key === key)
  return line?.value ?? null
}

export function readAllEnvValues(envFile: EnvFile, keys: string[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const key of keys) {
    const val = readEnvValue(envFile, key)
    if (val !== null) result[key] = val
  }
  return result
}

export async function writeEnvValues(filePath: string, values: Record<string, string>): Promise<void> {
  const envFile = await parseEnvFile(filePath)
  const keysToWrite = new Set(Object.keys(values))

  // Update existing entries
  for (const line of envFile.lines) {
    if (line.type === 'entry' && line.key && keysToWrite.has(line.key)) {
      line.value = values[line.key]
      line.raw = `${line.key}=${values[line.key]}`
      keysToWrite.delete(line.key)
    }
  }

  // Append new keys at the end
  for (const key of keysToWrite) {
    envFile.lines.push({ type: 'entry', raw: `${key}=${values[key]}`, key, value: values[key] })
  }

  const output = envFile.lines.map((l) => l.raw).join('\n')
  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(filePath, output, 'utf-8')
}

export async function migrateGithubToken(filePath: string): Promise<boolean> {
  const envFile = await parseEnvFile(filePath)
  const oldLine = envFile.lines.find((l) => l.type === 'entry' && l.key === 'GITHUB_HF_PM_OS')
  const newLine = envFile.lines.find((l) => l.type === 'entry' && l.key === 'GITHUB_API_TOKEN')

  if (!oldLine || oldLine.key !== 'GITHUB_HF_PM_OS') return false
  if (newLine) return false // already migrated

  // Rename the old key
  oldLine.key = 'GITHUB_API_TOKEN'
  oldLine.raw = `GITHUB_API_TOKEN=${oldLine.value}`

  const output = envFile.lines.map((l) => l.raw).join('\n')
  fs.writeFileSync(filePath, output, 'utf-8')
  return true
}
