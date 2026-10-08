/* SPDX-License-Identifier: Apache-2.0
 * Annotated recording of the real local UI and its real memory rejection.
 * Sends ONE image request; never sends text/video requests or starts models itself.
 * Requires Playwright/Chromium and FFmpeg/FFprobe, separately installed.
 */
'use strict';

const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const origin = 'http://127.0.0.1:18766';
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

async function main() {
  const frameRoot = path.join(root, 'runtime_cache');
  await fs.mkdir(frameRoot, { recursive: true });
  const temporary = await fs.mkdtemp(path.join(frameRoot, 'walkthrough-'));
  const browser = await chromium.launch({ headless: true, args: ['--disable-gpu'] });
  const shots = [], steps = [], failures = [];
  let postCount = 0, result;
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      const localGet = request.method() === 'GET' && ['/', '/health', '/jobs', '/favicon.ico'].includes(url.pathname);
      const imagePost = request.method() === 'POST' && url.pathname === '/jobs/image' && postCount === 0;
      if (url.origin !== origin || (!localGet && !imagePost)) {
        failures.push('Blocked unexpected request: ' + request.method() + ' ' + url.pathname);
        return route.abort();
      }
      if (imagePost) postCount++;
      if (url.pathname === '/jobs') {
        const response = await route.fetch();
        const data = await response.json();
        if (!response.ok() || !Array.isArray(data.jobs) || data.jobs.length) {
          failures.push('The queue is not empty. Stop recording; do not expose private jobs.');
          return route.abort();
        }
        // Preserve the real response, do not manufacture queue states.
        return route.fulfill({ response });
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => failures.push(error.message));
    const healthPromise = page.waitForResponse(origin + '/health');
    const jobsPromise = page.waitForResponse(origin + '/jobs');
    const initialPage = await page.goto(origin, { waitUntil: 'domcontentloaded' });
    if (!initialPage.ok()) throw new Error('The local workbench is unavailable.');
    const health = await (await healthPromise).json();
    const jobs = await (await jobsPromise).json();
    if (health.service !== 'local-free-gateway' || health.jobs !== 0 || jobs.jobs.length) throw new Error('Expected an empty real workbench.');
    if (!health.memory.supported || health.memory.image_ready !== false) {
      throw new Error('This recording is specifically for the real memory-rejection path; no request was submitted.');
    }
    await page.waitForFunction(() => document.querySelector('#jobs').textContent.includes('还没有任务'));
    await page.evaluate(() => document.fonts.ready);

    // Recording annotations only: do not change service results or simulate outputs.
    await page.addStyleTag({ content: `
      body { padding-top: 110px; padding-bottom: 50px; }
      #recording-guide { position: fixed; inset: 0 0 auto; z-index: 100000;
        height: 104px; padding: 15px 30px; background: #101d1b; border-bottom: 2px solid #bde98e;
        font-family: system-ui, "Microsoft YaHei", sans-serif; color: #f0f3ed; pointer-events: none; }
      #recording-guide strong { display: block; font-size: 23px; line-height: 1.4; }
      #recording-guide p { margin: 6px 0 0; font-size: 16px; line-height: 1.45; color: #d1dfd8; }
      #recording-guide span { position: absolute; top: 18px; right: 28px; font-size: 13px; color: #fbd08c; }
      [data-recording-focus] { outline: 3px solid #f3c76f !important; outline-offset: 5px; }
      #recording-pointer { position: fixed; z-index: 100001; pointer-events: none; width: 22px; height: 22px;
        border: 3px solid #fff; border-radius: 50%; background: #e8af47aa; transform: translate(-50%, -50%); display: none; }
    ` });
    await page.evaluate(() => {
      const guide = document.createElement('aside'); guide.id = 'recording-guide';
      guide.innerHTML = '<strong></strong><p></p><span>操作演示 · 尚未生成成片</span>';
      const pointer = document.createElement('div'); pointer.id = 'recording-pointer';
      document.body.append(guide, pointer);
    });

    async function frame(seconds) {
      if (failures.length || await page.locator('#jobs article').count()) throw new Error(failures.join('\n') || 'Private jobs appeared.');
      const name = String(shots.length).padStart(4, '0') + '.png';
      await page.screenshot({ path: path.join(temporary, name) });
      shots.push({ file: name, duration: seconds });
    }
    async function step(title, description, target) {
      steps.push({ title, description });
      await page.evaluate(({ title, description }) => {
        document.querySelector('#recording-guide strong').textContent = title;
        document.querySelector('#recording-guide p').textContent = description;
        document.querySelectorAll('[data-recording-focus]').forEach(el => el.removeAttribute('data-recording-focus'));
        document.querySelector('#recording-pointer').style.display = 'none';
      }, { title, description });
      if (target) {
        await page.locator(target).evaluate(el => { el.scrollIntoView({ block: 'center' }); el.setAttribute('data-recording-focus', ''); });
      } else { await page.evaluate(() => window.scrollTo(0, 0)); }
    }
    async function point(selector) {
      const box = await page.locator(selector).boundingBox();
      if (!box) throw new Error('Control is not visible: ' + selector);
      const x = box.x + box.width / 2, y = box.y + box.height / 2;
      await page.mouse.move(x, y);
      await page.evaluate(({ x, y }) => {
        Object.assign(document.querySelector('#recording-pointer').style, { display: 'block', left: x + 'px', top: y + 'px' });
      }, { x, y });
    }
    async function fillGradually(selector, text) {
      await point(selector);
      await page.locator(selector).fill('');
      await frame(0.2);
      for (let length = 0; length < text.length; length += 40) {
        await page.locator(selector).fill(text.slice(0, length + 40));
        await frame(0.25);
      }
    }

    await step('01 / 先检查本机服务与内存', '真实界面录制：当前内存不足；下面演示操作与真实拦截，不展示生成成功。');
    await frame(2.8);
    await step('02 / 填写剧本需求（也可直接使用自己的提示词）', '文本入口使用本机 CPU。本次只填写示例，不启动语言模型。', '#textForm');
    await fillGradually('#textPrompt', '原创古装悬疑短剧：成年女侦探在庭院发现线索。拆成三个短镜头，每镜只安排一个动作，给出中文剧情和英文提示词。');
    await frame(1.8);
    await step('03 / 写清静帧：人物、构图、光线和背景', '先检查清晰的脸和合理构图，再把合格静帧用于图生视频。', '#imageForm');
    await fillGradually('#imagePrompt', 'Original adult female detective in a teal hanfu, medium close-up in a stone courtyard, clear eyes and facial features, soft daylight, detailed background, no text or watermark.');
    await frame(1.2);
    await step('04 / 选择画幅，固定种子方便复查', '示例：竖屏 720 × 1280。固定 seed 有助于记录，但不保证角色跨镜头一致。', '#imageForm');
    await point('#ratio'); await page.locator('#ratio').selectOption('9:16'); await frame(0.8);
    await point('#imageSeed'); await page.locator('#imageSeed').fill('146500601'); await frame(1.4);
    await step('05 / 点击“静帧加入队列”', '本次会实际提交一次图片请求；保留网关返回的真实结果，不绕过内存预检。', '#imageForm');
    const before = await page.evaluate(async () => (await fetch('/health')).json());
    if (before.memory.image_ready !== false) throw new Error('Memory conditions changed. Stopped before submission.');
    await point('#imageForm button'); await frame(1.2);
    const submitted = page.waitForResponse(response => response.url() === origin + '/jobs/image' && response.request().method() === 'POST');
    await page.locator('#imageForm button').click();
    const response = await submitted, body = await response.json();
    if (response.status() !== 503 || typeof body.detail !== 'string' || !body.detail.includes('可用提交内存不足')) {
      throw new Error('Unexpected submission result, HTTP ' + response.status() + '. Recording stopped; inspect the live queue before retrying.');
    }
    await page.waitForFunction(() => document.querySelector('#message').textContent.includes('可用提交内存不足'));
    await step('06 / 看懂返回：内存不足，没有入队', '真实 HTTP 503：先保存工作、释放内存再刷新。不要反复点击，也不要关闭保护。', '#message');
    await frame(3.6);
    await step('07 / 合格静帧 → 视频首帧', '这里只用已公开的工作台截图演示选文件；不是人物首帧，不会提交它生成视频。', '#videoForm');
    await point('#firstFrame'); await frame(1.0);
    await page.locator('#firstFrame').setInputFiles({
      name: 'upload-demo-only.png', mimeType: 'image/png',
      buffer: await fs.readFile(path.join(root, 'docs', 'screenshots', 'workbench-overview.png')),
    });
    await frame(2.0);
    await step('08 / 设置一个简单动作与短镜头时长', '示例：缓慢转头、轻微推进；从约 2 秒开始，生成后仍需人工审片。', '#videoForm');
    await fillGradually('#videoPrompt', 'The woman slowly turns her head toward the courtyard door. Keep her face and clothing consistent. The camera gently pushes closer. One continuous shot, stable background.');
    await point('#duration'); await page.locator('#duration').selectOption('2'); await frame(1.5);
    await step('09 / 实际制作时，审查首帧后再提交动态镜头', '当前内存未通过，且所选文件仅用于演示。本次不点击视频提交、不启动 GPU 推理。', '#videoForm');
    await point('#videoForm button'); await frame(2.8);
    await step('10 / 到任务区查看状态与素材', '当前确实没有任务。真正生成成功后才会出现预览和保存入口；随后人工审片。', '#jobs');
    await page.locator('#jobs').waitFor({ state: 'visible' });
    await frame(3.0);
    const finalJobs = await page.evaluate(async () => (await fetch('/jobs')).json());
    if (failures.length || finalJobs.jobs.length || postCount !== 1) throw new Error(failures.join('\n') || 'Final queue verification failed.');
    result = {
      captured_at: new Date().toISOString(), source: 'Real local workbench with clearly labeled recording annotations',
      viewport: { width: 1280, height: 900 }, browser: browser.version(),
      html_sha256: sha256((await fs.readFile(path.join(root, 'app', 'static', 'local_free.html'), 'utf8')).replace(/\r\n/g, '\n')),
      mocked_api_responses: false, edited_timing: true, image_requests: postCount,
      image_response_status: response.status(), image_response_detail: body.detail,
      video_requests: 0, text_requests: 0, final_jobs: 0,
      upload_demo_source: 'docs/screenshots/workbench-overview.png',
      upload_demo_sha256: sha256(await fs.readFile(path.join(root, 'docs', 'screenshots', 'workbench-overview.png'))),
      steps,
    };
  } finally { await browser.close(); }

  const concat = 'ffconcat version 1.0\n' + shots.map(shot => `file '${shot.file}'\nduration ${shot.duration}\n`).join('') + `file '${shots.at(-1).file}'\n`;
  await fs.writeFile(path.join(temporary, 'frames.ffconcat'), concat);
  const output = path.join(temporary, 'generation-walkthrough.gif');
  execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
    '-i', path.join(temporary, 'frames.ffconcat'), '-filter_complex',
    '[0:v]fps=8,split[a][b];[a]palettegen=max_colors=256:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle',
    '-loop', '0', output], { windowsHide: true, timeout: 60000 });
  const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-count_frames', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height,nb_read_frames:format=duration', '-of', 'json', output], { windowsHide: true }).toString());
  const data = await fs.readFile(output);
  if (data.length > 8 * 1024 ** 2) throw new Error('GIF exceeds the README size budget.');
  const destination = path.join(root, 'docs', 'screenshots');
  await fs.copyFile(output, path.join(destination, 'generation-walkthrough.gif'));
  result.asset = { file: 'generation-walkthrough.gif', bytes: data.length, sha256: sha256(data),
    width: probe.streams[0].width, height: probe.streams[0].height,
    frames: Number(probe.streams[0].nb_read_frames), duration_seconds: Number(probe.format.duration) };
  result.capture_frames = shots.length;
  await fs.writeFile(path.join(destination, 'walkthrough-manifest.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result.asset));
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
