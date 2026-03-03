#!/usr/bin/env node
const { spawnSync } = require('child_process');
const path = require('path');

const action = process.argv[2] || 'build';
const valid = new Set(['start', 'build', 'test']);
if (!valid.has(action)) {
  console.error(`Invalid action: ${action}`);
  process.exit(1);
}

const localBin = path.join(__dirname, '..', 'node_modules', '.bin', 'react-scripts');

function run(cmd, args) {
  const res = spawnSync(cmd, args, { stdio: 'inherit', shell: true, env: process.env });
  if (typeof res.status === 'number') return res.status;
  return 1;
}

let code = run(localBin, [action]);
if (code === 0) process.exit(0);

console.warn('[runner] local react-scripts not found/failed. Trying npx fallback...');
code = run('npx', ['--yes', 'react-scripts@5.0.1', action]);
process.exit(code);
