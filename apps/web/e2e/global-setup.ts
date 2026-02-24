/**
 * Playwright global setup — switch avatar-engine to a cheap model for E2E tests.
 *
 * Reads ~/.synapse/avatar.yaml, saves the original gemini model,
 * and replaces it with gemini-2.0-flash to save API costs during testing.
 * The original is restored in global-teardown.ts.
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import * as os from 'node:os'

const AVATAR_YAML = path.join(os.homedir(), '.synapse', 'avatar.yaml')
const BACKUP_SUFFIX = '.e2e-backup'

/** Model to use during E2E tests (cheap & fast) */
const TEST_MODEL = 'gemini-2.0-flash'

export default async function globalSetup() {
  if (!fs.existsSync(AVATAR_YAML)) {
    console.log('[e2e-setup] No avatar.yaml found — skipping model switch')
    return
  }

  const content = fs.readFileSync(AVATAR_YAML, 'utf-8')

  // Save backup of the original file
  fs.writeFileSync(AVATAR_YAML + BACKUP_SUFFIX, content, 'utf-8')

  // Replace gemini model line: `  model: "anything"` → `  model: "gemini-2.0-flash"`
  const updated = content.replace(
    /(gemini:\s*\n\s*model:\s*)"[^"]*"/,
    `$1"${TEST_MODEL}"`,
  )

  if (updated !== content) {
    fs.writeFileSync(AVATAR_YAML, updated, 'utf-8')
    console.log(`[e2e-setup] Switched gemini model to ${TEST_MODEL}`)
  } else {
    console.log('[e2e-setup] Could not find gemini model line — keeping as-is')
  }
}
