/**
 * Playwright global teardown — restore original avatar-engine model.
 *
 * Reads the backup created by global-setup.ts and restores
 * the original ~/.synapse/avatar.yaml content.
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import * as os from 'node:os'

const AVATAR_YAML = path.join(os.homedir(), '.synapse', 'avatar.yaml')
const BACKUP_SUFFIX = '.e2e-backup'

export default async function globalTeardown() {
  const backupPath = AVATAR_YAML + BACKUP_SUFFIX

  if (!fs.existsSync(backupPath)) {
    return
  }

  const original = fs.readFileSync(backupPath, 'utf-8')
  fs.writeFileSync(AVATAR_YAML, original, 'utf-8')
  fs.unlinkSync(backupPath)
  console.log('[e2e-teardown] Restored original avatar.yaml')
}
