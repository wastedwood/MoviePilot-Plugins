/**
 * 按官方模块联邦指南过滤构建产物，复制到插件目录：
 * 只保留 remoteEntry.js、__federation_ 前缀、_plugin-vue_export-helper 前缀；
 * 严禁 index / date / runtime 前缀与 __federation_shared 目录（会污染宿主）。
 */
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const assets = join(here, '..', 'dist', 'assets')
const target = join(here, '..', '..', 'plugins.v2', 'fntvdoubansync', 'dist', 'assets')

const ALLOW = [/^remoteEntry\.js$/, /^__federation_/, /^_plugin-vue_export-helper-/]
const DENY = [/^index-/, /^date-/, /^runtime-/, /^__federation_shared_/]

if (!existsSync(assets)) {
  console.error('未找到 dist/assets，请先执行 vite build')
  process.exit(1)
}

rmSync(target, { recursive: true, force: true })
mkdirSync(target, { recursive: true })

const files = readdirSync(assets)
const kept = []
for (const file of files) {
  if (DENY.some(re => re.test(file))) continue
  if (ALLOW.some(re => re.test(file))) {
    cpSync(join(assets, file), join(target, file))
    kept.push(file)
  }
}

const missing = []
if (!kept.includes('remoteEntry.js')) missing.push('remoteEntry.js')
if (!kept.some(f => /^__federation_expose_/.test(f))) missing.push('__federation_expose_*')

if (missing.length) {
  console.error(`产物不完整，缺少：${missing.join('、')}`)
  process.exit(1)
}

console.log(`已复制 ${kept.length} 个联邦产物 → ${target}`)
for (const file of kept.sort()) console.log(`  ${file}`)
