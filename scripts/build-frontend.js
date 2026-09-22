const { spawnSync } = require('child_process');
const path = require('path');

const rootDir = path.join(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const tscCli = path.join(frontendDir, 'node_modules', 'typescript', 'bin', 'tsc');
const viteCli = path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js');

console.log('[BUILD] Step 1: Typecheck with TypeScript...');
const tscRes = spawnSync(process.execPath, [tscCli, '--noEmit', '--project', path.join(frontendDir, 'tsconfig.json')], {
  cwd: frontendDir,
  stdio: 'inherit'
});

if (tscRes.status !== 0) {
  console.error(`[BUILD] TypeScript typecheck failed with code ${tscRes.status}`);
  process.exit(tscRes.status || 1);
}
console.log('[BUILD] TypeScript typecheck passed! (code 0)');

console.log('[BUILD] Step 2: Bundling with Vite...');
const viteRes = spawnSync(process.execPath, [viteCli, 'build'], {
  cwd: frontendDir,
  stdio: 'inherit'
});

if (viteRes.status !== 0) {
  console.error(`[BUILD] Vite build failed with code ${viteRes.status}`);
  process.exit(viteRes.status || 1);
}

console.log('[BUILD] Vite production build completed successfully! (code 0)');
process.exit(0);
