/* SPDX-License-Identifier: Apache-2.0
 * Capture the real, empty local workbench. Never submit generation jobs.
 * Requires a separately installed Playwright + Chromium; see docs/SCREENSHOTS.md.
 */
'use strict';

const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');

const origin = 'http://127.0.0.1:18766';
const root = path.resolve(__dirname, '..');
const destination = path.join(root, 'docs', 'screenshots');
const allowedPaths = new Set(['/', '/health', '/jobs', '/favicon.ico']);

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--disable-gpu'] });
  const failures = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
    // No external services, POSTs, or generated-media requests are allowed.
    await context.route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() !== 'GET' || url.origin !== origin || !allowedPaths.has(url.pathname)) {
        failures.push('Blocked request: ' + request.method() + ' ' + url.pathname);
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => failures.push(error.message));
    const healthResponse = page.waitForResponse(origin + '/health');
    const jobsResponse = page.waitForResponse(origin + '/jobs');
    const response = await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
    if (!response || !response.ok()) throw new Error('The local workbench is not available.');
    const healthResult = await healthResponse;
    const jobsResult = await jobsResponse;
    if (!healthResult.ok() || !jobsResult.ok()) throw new Error('Local read-only API check failed.');
    const health = await healthResult.json();
    const jobs = await jobsResult.json();
    if (health.service !== 'local-free-gateway') throw new Error('Unexpected service on port 18766.');
    if (!Array.isArray(jobs.jobs) || jobs.jobs.length || health.jobs !== 0) {
      throw new Error('Capture requires an empty queue to avoid publishing private prompts or assets.');
    }
    await page.waitForFunction(() => {
      const state = document.querySelector('#readiness');
      const jobs = document.querySelector('#jobs');
      return state && !state.textContent.includes('检查中') && jobs && jobs.textContent.includes('还没有任务');
    });
    await page.evaluate(() => document.fonts.ready);
    await fs.mkdir(destination, { recursive: true });

    const files = [];
    async function capture(filename, action) {
      const output = path.join(destination, filename);
      await action(output);
      const buffer = await fs.readFile(output);
      files.push({ file: filename, width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20),
        sha256: crypto.createHash('sha256').update(buffer).digest('hex') });
    }
    await capture('workbench-overview.png', output => page.screenshot({ path: output, fullPage: true }));
    const imagePanel = page.locator('section').filter({ has: page.locator('#imageForm') });
    const videoPanel = page.locator('section').filter({ has: page.locator('#videoForm') });
    const imageBox = await imagePanel.boundingBox();
    const videoBox = await videoPanel.boundingBox();
    if (!imageBox || !videoBox) throw new Error('Generation panels are missing.');
    await capture('generation-panels.png', output => page.screenshot({ path: output, fullPage: true, clip: {
      x: Math.min(imageBox.x, videoBox.x),
      y: Math.min(imageBox.y, videoBox.y),
      width: Math.max(imageBox.x + imageBox.width, videoBox.x + videoBox.width) - Math.min(imageBox.x, videoBox.x),
      height: Math.max(imageBox.y + imageBox.height, videoBox.y + videoBox.height) - Math.min(imageBox.y, videoBox.y),
    } }));
    await page.getByText('技术检查详情', { exact: true }).click();
    await page.getByText('画质与使用边界', { exact: true }).click();
    const servicePanel = page.locator('section').filter({ has: page.locator('#readiness') });
    await capture('service-status.png', output => servicePanel.screenshot({ path: output }));

    // Recheck the real queue immediately before accepting the captures.
    const finalJobs = await page.evaluate(async () => (await fetch('/jobs')).json());
    if (!Array.isArray(finalJobs.jobs) || finalJobs.jobs.length) throw new Error('Queue changed during capture. Do not publish the captures.');
    if (failures.length) throw new Error(failures.join('\n'));
    const source = (await fs.readFile(path.join(root, 'app', 'static', 'local_free.html'), 'utf8')).replace(/\r\n/g, '\n');
    const manifest = {
      captured_at: new Date().toISOString(),
      source: 'Real localhost workbench, no mock data or generated-media examples',
      viewport: { width: 1440, height: 1100, device_scale_factor: 1 },
      generation_panels_expected_size: {
        width: Math.ceil(Math.max(imageBox.x + imageBox.width, videoBox.x + videoBox.width) - Math.min(imageBox.x, videoBox.x)),
        height: Math.ceil(Math.max(imageBox.y + imageBox.height, videoBox.y + videoBox.height) - Math.min(imageBox.y, videoBox.y)),
      },
      browser: browser.version(),
      html_sha256: crypto.createHash('sha256').update(source).digest('hex'),
      ready: health.ready,
      jobs: jobs.jobs.length,
      cloud_fallback: health.cloud_fallback,
      memory: health.memory,
      files,
    };
    await fs.writeFile(path.join(destination, 'capture-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
    console.log(JSON.stringify({ captured: files.map(item => item.file), ready: health.ready, jobs: 0 }));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
