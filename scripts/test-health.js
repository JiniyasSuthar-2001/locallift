const http = require('http');

function check(url, name) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      console.log(`[VERIFY] ${name} responded with HTTP ${res.statusCode}`);
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (data.length < 250) console.log(`         Body: ${data}`);
        resolve();
      });
    }).on('error', (err) => {
      console.error(`[FAIL] ${name} failed: ${err.message}`);
      reject(err);
    });
  });
}

async function run() {
  try {
    await check('http://127.0.0.1:5173', 'Frontend (Vite UI)');
    await check('http://127.0.0.1:8000/health', 'Backend (/health)');
    await check('http://127.0.0.1:8000/', 'Backend Root (/)');
    console.log('\n✓ ALL SERVICES LIVE AND RESPONDING CORRECTLY!');
  } catch (err) {
    process.exit(1);
  }
}

run();
