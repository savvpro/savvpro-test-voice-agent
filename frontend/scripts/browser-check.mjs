// Optional full-stack check using only Node built-ins and an installed browser.
// Every backend write goes to a new temporary database, never the development DB.
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { access, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const temporary = await mkdtemp(path.join(os.tmpdir(), 'golden-fork-e2e-'));
const database = path.join(temporary, 'restaurant.sqlite3');
const children = [];
let socket;

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function launch(command, args, cwd = root, extraEnv = {}) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...extraEnv }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  child.output = '';
  child.stdout.on('data', (data) => { child.output += data; });
  child.stderr.on('data', (data) => { child.output += data; });
  child.once('error', (error) => { child.launchError = error; });
  children.push(child);
  return child;
}

async function until(predicate, label, timeout = 25_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    for (const child of children) {
      if (child.launchError) throw child.launchError;
      if (child.exitCode !== null) throw new Error(`Child exited: ${child.output}`);
    }
    try { const result = await predicate(); if (result) return result; } catch (error) {
      if (error instanceof assert.AssertionError) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out: ${label}`);
}

async function browserPath() {
  const candidates = [process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium'];
  for (const candidate of candidates.filter(Boolean)) {
    try { await access(candidate); return candidate; } catch { /* Try the next installed browser. */ }
  }
  throw new Error('No Chrome/Edge found. Set CHROME_PATH to an installed Chromium browser.');
}

try {
  const backendPort = await freePort();
  const frontendPort = await freePort();
  const browserPort = await freePort();
  const backendUrl = `http://127.0.0.1:${backendPort}`;
  const frontendUrl = `http://127.0.0.1:${frontendPort}`;
  launch(process.env.PYTHON || 'python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)], path.resolve(root, '../backend'), { DATABASE_PATH: database });
  launch(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(frontendPort)], root, { API_PROXY_TARGET: backendUrl });
  await until(async () => (await fetch(`${backendUrl}/api/health`)).ok, 'backend readiness');
  await until(async () => (await fetch(frontendUrl)).ok, 'frontend readiness');
  assert.equal((await fetch(`${frontendUrl}/api/health`)).status, 200);

  launch(await browserPath(), ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', `--remote-debugging-port=${browserPort}`, `--user-data-dir=${path.join(temporary, 'browser-profile')}`, 'about:blank']);
  const page = await until(async () => {
    const response = await fetch(`http://127.0.0.1:${browserPort}/json/new?${encodeURIComponent(frontendUrl)}`, { method: 'PUT' });
    return response.ok ? response.json() : null;
  }, 'browser readiness');

  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  let sequence = 0;
  const commands = new Map();
  const browserErrors = [];
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') browserErrors.push(message.params.exceptionDetails.text);
    const pending = commands.get(message.id);
    if (pending) {
      commands.delete(message.id);
      if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
      else pending.resolve(message.result);
    }
  });
  function command(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      commands.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }
  async function evaluate(expression) {
    const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
    return response.result.value;
  }
  const saved = () => evaluate("JSON.parse(sessionStorage.getItem('golden-fork-conversation-v1'))");
  const click = (text) => evaluate(`Array.from(document.querySelectorAll('button')).find(button => button.textContent.trim() === ${JSON.stringify(text)}).click()`);
  const count = () => Number(execFileSync(process.env.PYTHON || 'python', ['-c', 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT count(*) FROM reservations").fetchone()[0]); c.close()', database], { windowsHide: true, encoding: 'utf8' }).trim());
  async function send(text, expectedStatus) {
    const before = (await saved()).messages.length;
    await evaluate(`(() => { const input = document.querySelector('textarea'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(input, ${JSON.stringify(text)}); input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
    await until(() => evaluate("!document.querySelector('[aria-label=\"Send message\"]').disabled"), 'enabled send button');
    await evaluate("document.querySelector('[aria-label=\"Send message\"]').click()");
    await until(async () => { const state = await saved(); return !state.busy && !state.pending && state.messages.length > before && state.conversation.status === expectedStatus; }, expectedStatus);
  }
  async function screenshot(name) {
    const metrics = await command('Page.getLayoutMetrics');
    const size = metrics.cssContentSize;
    const shot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: Math.ceil(size.width), height: Math.ceil(size.height), scale: 1 } });
    await writeFile(path.join(root, 'artifacts', name), Buffer.from(shot.data, 'base64'));
  }

  await command('Runtime.enable');
  await command('Page.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await until(() => evaluate("!!document.querySelector('.start-button')"), 'React application');
  await mkdir(path.join(root, 'artifacts'), { recursive: true });
  await screenshot('desktop.png');
  await click('Start Conversation');
  await until(async () => Boolean((await saved())?.conversation?.session_id), 'new session');
  const originalSession = (await saved()).conversation.session_id;
  await send('tomorrow at 7pm for 4', 'confirm');
  assert.equal(count(), 0);
  await send('not correct', 'confirm');
  assert.equal(count(), 0);
  await send('actually 6 people', 'confirm');
  assert.equal(count(), 0);
  await send('yes', 'completed');
  const complete = await saved();
  assert.equal(complete.conversation.reservation.party_size, 6);
  assert.ok(complete.conversation.reservation.reservation_id);
  const keys = complete.messages.filter((item) => item.role === 'customer').map((item) => item.id);
  assert.equal(new Set(keys).size, 4);
  assert.equal(count(), 1);

  // Wait for a NEW document, not a success card still in the pre-reload DOM.
  await evaluate('window.__goldenForkBeforeReload = true');
  await command('Page.reload');
  await until(() => evaluate("document.readyState === 'complete' && !window.__goldenForkBeforeReload && document.querySelector('.success-card')?.textContent.includes('Your table is booked.')"), 'restored completed reservation');
  assert.equal((await saved()).conversation.reservation.reservation_id, complete.conversation.reservation.reservation_id);
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await until(() => evaluate("innerWidth === 390 && !!document.querySelector('.message-area') && !!document.querySelector('.success-card')"), 'mobile viewport');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, 'mobile horizontal overflow');
  await evaluate("(() => { const area = document.querySelector('.message-area'); area.scrollTop = area.scrollHeight; })()");
  await screenshot('mobile.png');
  await click('New conversation');
  await until(async () => (await saved())?.conversation?.session_id !== originalSession, 'new independent session');
  assert.equal(await evaluate("!!document.querySelector('.success-card')"), false);
  assert.equal(count(), 1);

  // Real microphone/audio services are not reliable in headless CI. Install
  // browser API mocks, while keeping React, the proxy, Python, and SQLite real.
  await command('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__voiceCheck = { spoken: [], cancellations: 0, recognition: null };
    window.SpeechRecognition = class {
      start() { window.__voiceCheck.recognition = this; this.onstart?.(); }
      stop() { this.onaudioend?.(); }
      abort() { this.onend?.(); }
    };
    window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
      speak(utterance) { window.__voiceCheck.spoken.push(utterance.text); utterance.onstart?.(); },
      cancel() { window.__voiceCheck.cancellations++; }
    } });
  ` });
  await evaluate('window.__goldenForkBeforeReload = true');
  await command('Page.reload');
  await until(() => evaluate("document.readyState === 'complete' && !window.__goldenForkBeforeReload && !!window.__voiceCheck && !!document.querySelector('textarea')"), 'voice check readiness');
  await evaluate("document.querySelector('.spoken-toggle input').click()");
  assert.equal(await evaluate('window.__voiceCheck.spoken.length'), 0, 'do not replay restored history');

  async function dictate(text) {
    await until(() => evaluate("!document.querySelector('.microphone-button').disabled"), 'enabled microphone');
    const before = (await saved()).messages.length;
    await evaluate("document.querySelector('.microphone-button').click()");
    await until(() => evaluate('!!window.__voiceCheck.recognition'), 'listening');
    await evaluate(`(() => {
      const recognition = window.__voiceCheck.recognition;
      const result = [{ transcript: ${JSON.stringify(text)} }];
      result.isFinal = true;
      recognition.onresult({ results: [result] });
      recognition.onend();
    })()`);
    await until(() => evaluate(`document.querySelector('textarea').value === ${JSON.stringify(text)} && !document.querySelector('textarea').disabled`), 'editable transcript');
    assert.equal((await saved()).messages.length, before, 'dictation must not auto-send');
  }

  await dictate('tomorrow at 8:30pm for 2');
  assert.equal(count(), 1);
  await send('tomorrow at 8:30pm for 3', 'confirm'); // Correct the recognized count before sending.
  assert.equal((await saved()).conversation.collected_data.party_size, 3);
  assert.equal(count(), 1);
  await until(() => evaluate('window.__voiceCheck.spoken.length === 1'), 'spoken confirmation prompt');
  await click('Stop speaking');
  assert.ok(await evaluate('window.__voiceCheck.cancellations > 0'));
  await dictate('yes');
  assert.equal(count(), 1);
  await send('yes', 'completed');
  await until(() => evaluate('window.__voiceCheck.spoken.length === 2'), 'spoken committed reservation');
  assert.equal(count(), 2);
  assert.equal((await saved()).conversation.reservation.party_size, 3);
  await evaluate("document.querySelector('.spoken-toggle input').click()");
  await evaluate("document.querySelector('.spoken-toggle input').click()");
  assert.equal(await evaluate('window.__voiceCheck.spoken.length'), 2, 'enabling playback must not replay a reply');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true, 'voice controls mobile overflow');
  assert.deepEqual(browserErrors, []);
  console.log('PASS: Vite proxy, start, details, rejection, correction, confirmation, reload, and new conversation.');
  console.log('PASS: one text-flow booking plus one voice-flow booking in temporary SQLite; four unique text-flow message IDs.');
  console.log('PASS: mocked dictation -> editable correction -> existing API -> explicit voice confirmation; no auto-send.');
  console.log('PASS: mocked spoken replies, Stop speaking, and no replay when toggled or rerendered.');
  console.log('PASS: desktop and 390px mobile rendering; no horizontal overflow or browser exceptions.');
  console.log('Screenshots: frontend/artifacts/desktop.png and frontend/artifacts/mobile.png');
} finally {
  socket?.close();
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      const exited = new Promise((resolve) => { child.once('exit', resolve); setTimeout(resolve, 3000).unref(); });
      child.kill();
      await exited;
    }
  }
  // Only remove the fresh directory this script created under the temp root.
  const resolved = path.resolve(temporary);
  assert.equal(path.dirname(resolved), path.resolve(os.tmpdir()));
  assert.ok(path.basename(resolved).startsWith('golden-fork-e2e-'));
  await rm(resolved, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
