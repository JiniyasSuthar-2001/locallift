const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

function getPythonCommand() {
  // Check virtualenvs if present
  const venvPythonWin = path.join(__dirname, '..', 'backend', 'venv', 'Scripts', 'python.exe');
  const venvPythonUnix = path.join(__dirname, '..', 'backend', 'venv', 'bin', 'python');
  if (fs.existsSync(venvPythonWin)) return venvPythonWin;
  if (fs.existsSync(venvPythonUnix)) return venvPythonUnix;

  // Windows fallback paths
  if (process.platform === 'win32') {
    const userLocalPython = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python313', 'python.exe');
    if (fs.existsSync(userLocalPython)) return userLocalPython;
  }

  // Check system commands
  const candidates = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      execSync(`"${cmd}" --version`, { stdio: 'ignore' });
      return cmd;
    } catch (e) {
      // Continue searching
    }
  }

  return 'python';
}

const pythonCmd = getPythonCommand();
const backendDir = path.join(__dirname, '..', 'backend');

const args = ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000', '--host', '127.0.0.1'];

const backendProcess = spawn(pythonCmd, args, {
  cwd: backendDir,
  stdio: 'inherit',
  shell: false
});

backendProcess.on('error', (err) => {
  console.error('\x1b[31m[BACKEND] ✗ Failed to start backend process:\x1b[0m', err.message);
  console.error('\x1b[33mEnsure Python 3.10+ and requirements are installed via: pip install -r backend/requirements.txt\x1b[0m');
  process.exit(1);
});

backendProcess.on('exit', (code) => {
  if (code !== 0 && code !== null) {
    console.error(`\x1b[31m[BACKEND] ✗ Process exited with code ${code}\x1b[0m`);
    process.exit(code);
  }
});
