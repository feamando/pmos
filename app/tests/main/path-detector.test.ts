import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import { validateEnvPath } from '../../src/main/env/path-detector'

let tmpDir: string

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pmos-path-test-'))
})

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true })
})

describe('validateEnvPath', () => {
  it('returns true for existing file', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, 'KEY=val')
    expect(await validateEnvPath(filePath)).toBe(true)
  })

  it('returns false for missing file', async () => {
    expect(await validateEnvPath(path.join(tmpDir, 'nope.env'))).toBe(false)
  })

  it('returns false for directory', async () => {
    expect(await validateEnvPath(tmpDir)).toBe(false)
  })
})
