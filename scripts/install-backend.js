const { spawnSync, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.join(__dirname, '..');
const backendDir = path.join(rootDir, 'backend');
const venvDir = path.join(backendDir, 'venv');
const requirementsFile = path.join(backendDir, 'requirements.txt');

function getVenvPython() {
  const venvPythonWin = path.join(venvDir, 'Scripts', 'python.exe');
  const venvPythonUnix = path.join(venvDir, 'bin', 'python');
  if (process.platform === 'win32' && fs.existsSync(venvPythonWin)) return venvPythonWin;
  if (fs.existsSync(venvPythonUnix)) return venvPythonUnix;
  if (fs.existsSync(venvPythonWin)) return venvPythonWin;
  return null;
}

function getSystemPython() {
  if (process.platform === 'win32') {
    const userLocalPython = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python313', 'python.exe');
    if (fs.existsSync(userLocalPython)) return userLocalPython;
  }

  const candidates = process.platform === 'win32'
    ? ['py', 'python', 'python3']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      execSync(`"${cmd}" --version`, { stdio: 'ignore' });
      return cmd;
    } catch (e) {
      // Continue searching
    }
  }

  return process.platform === 'win32' ? 'python' : 'python3';
}

function ensureVenv() {
  let venvPython = getVenvPython();
  if (venvPython) {
    console.log(`\x1b[32m[BACKEND-INSTALL]\x1b[0m Existing virtual environment found at: ${venvDir}`);
    return venvPython;
  }

  console.log(`\x1b[36m[BACKEND-INSTALL]\x1b[0m Creating Python virtual environment at: ${venvDir}`);
  const systemPython = getSystemPython();

  const venvResult = spawnSync(systemPython, ['-m', 'venv', venvDir], {
    cwd: backendDir,
    stdio: 'inherit',
    shell: false
  });

  if (venvResult.status !== 0) {
    console.error(`\x1b[31m[BACKEND-INSTALL] ✗ Failed to create virtual environment with ${systemPython}.\x1b[0m`);
    process.exit(venvResult.status || 1);
  }

  venvPython = getVenvPython();
  if (!venvPython) {
    console.error('\x1b[31m[BACKEND-INSTALL] ✗ Virtualenv created but Python binary not found.\x1b[0m');
    process.exit(1);
  }

  console.log(`\x1b[32m[BACKEND-INSTALL] ✓ Virtual environment created successfully.\x1b[0m`);
  return venvPython;
}

function installRequirements(venvPython) {
  console.log(`\x1b[36m[BACKEND-INSTALL]\x1b[0m Installing backend requirements from ${requirementsFile}...`);

  const installResult = spawnSync(venvPython, ['-m', 'pip', 'install', '-r', requirementsFile], {
    cwd: backendDir,
    stdio: 'inherit',
    shell: false
  });

  if (installResult.status !== 0) {
    console.error(`\x1b[31m[BACKEND-INSTALL] ✗ Failed to install backend requirements (exit code ${installResult.status}).\x1b[0m`);
    process.exit(installResult.status || 1);
  }

  console.log(`\x1b[32m[BACKEND-INSTALL] ✓ Backend dependencies successfully installed into venv.\x1b[0m`);
}

const venvPython = ensureVenv();
installRequirements(venvPython);
