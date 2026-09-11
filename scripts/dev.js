const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

// Banner formatting
console.log('\x1b[36m╔══════════════════════════════════════════════╗\x1b[0m');
console.log('\x1b[36m║          LocalLift Development               ║\x1b[0m');
console.log('\x1b[36m╚══════════════════════════════════════════════╝\x1b[0m\n');
console.log('\x1b[90mStarting services...\x1b[0m\n');
console.log('\x1b[36m[FRONTEND]\x1b[0m Starting Vite Dev Server...');
console.log('\x1b[32m[BACKEND]\x1b[0m  Starting FastAPI Uvicorn Server...\n');

const rootDir = path.join(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const isWin = process.platform === 'win32';

let treeKill;
try {
  treeKill = require('tree-kill');
} catch (e) {
  treeKill = null;
}

// 1. Spawn Backend Process with proper quoting for paths with spaces
const backendScript = path.join(__dirname, 'start-backend.js');
const backendProc = spawn(
  process.execPath,
  [backendScript],
  {
    cwd: rootDir,
    shell: false,
    stdio: ['ignore', 'pipe', 'pipe']
  }
);

// 2. Spawn Frontend Process
const npmCmd = isWin ? 'npm.cmd' : 'npm';
const frontendProc = spawn(
  npmCmd,
  ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173'],
  {
    cwd: frontendDir,
    shell: isWin,
    stdio: ['ignore', 'pipe', 'pipe']
  }
);

let frontendReady = false;
let backendReady = false;

function checkReady() {
  if (frontendReady && backendReady) {
    console.log('\n\x1b[32m✓ LocalLift development environment ready\x1b[0m\n');
    console.log('\x1b[36m[FRONTEND]\x1b[0m \x1b[32m✓ Running at http://localhost:5173\x1b[0m');
    console.log('\x1b[32m[BACKEND]\x1b[0m  \x1b[32m✓ Running at http://localhost:8000\x1b[0m (API Docs: http://localhost:8000/docs)\n');
    console.log('\x1b[90mPress Ctrl+C to stop all services.\x1b[0m\n');
  }
}

// Pipe Frontend Logs with [FRONTEND] prefix
const rlFrontOut = readline.createInterface({ input: frontendProc.stdout });
rlFrontOut.on('line', (line) => {
  if (line.includes('Local:') || line.includes('ready in') || line.includes('VITE')) {
    if (!frontendReady) {
      frontendReady = true;
      checkReady();
    }
  }
  console.log(`\x1b[36m[FRONTEND]\x1b[0m ${line}`);
});

const rlFrontErr = readline.createInterface({ input: frontendProc.stderr });
rlFrontErr.on('line', (line) => {
  console.error(`\x1b[31m[FRONTEND]\x1b[0m ${line}`);
});

// Pipe Backend Logs with [BACKEND] prefix
const rlBackOut = readline.createInterface({ input: backendProc.stdout });
rlBackOut.on('line', (line) => {
  if (line.includes('Uvicorn running on') || line.includes('Application startup complete') || line.includes('Started server process')) {
    if (!backendReady) {
      backendReady = true;
      checkReady();
    }
  }
  console.log(`\x1b[32m[BACKEND]\x1b[0m  ${line}`);
});

const rlBackErr = readline.createInterface({ input: backendProc.stderr });
rlBackErr.on('line', (line) => {
  if (line.includes('Uvicorn running on') || line.includes('Application startup complete') || line.includes('Started server process')) {
    if (!backendReady) {
      backendReady = true;
      checkReady();
    }
  }
  console.log(`\x1b[32m[BACKEND]\x1b[0m  ${line}`);
});

// Graceful Shutdown Handler
let isCleaningUp = false;
function cleanup() {
  if (isCleaningUp) return;
  isCleaningUp = true;
  console.log('\n\x1b[90mShutting down all LocalLift services...\x1b[0m');
  
  const killProc = (proc) => {
    if (!proc || !proc.pid) return;
    if (treeKill) {
      treeKill(proc.pid, 'SIGTERM', () => {});
    } else {
      try {
        proc.kill('SIGTERM');
      } catch (e) {}
    }
  };

  killProc(frontendProc);
  killProc(backendProc);

  setTimeout(() => {
    process.exit(0);
  }, 400);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);
process.on('exit', cleanup);

backendProc.on('exit', (code) => {
  if (code !== 0 && code !== null && !isCleaningUp) {
    console.error(`\x1b[31m[BACKEND] ✗ Failed / Exited with code ${code}\x1b[0m`);
    cleanup();
  }
});

frontendProc.on('exit', (code) => {
  if (code !== 0 && code !== null && !isCleaningUp) {
    console.error(`\x1b[31m[FRONTEND] ✗ Failed / Exited with code ${code}\x1b[0m`);
    cleanup();
  }
});
