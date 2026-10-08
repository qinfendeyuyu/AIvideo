// Run: node --experimental-vm-modules tests/test_toonflow_provider_contract.mjs
// Protocol test in the app project, not in the read-only Toonflow upstream clone.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { stripTypeScriptTypes } from 'node:module';
import { createContext, SourceTextModule } from 'node:vm';

const source = await readFile(new URL('../integrations/toonflow/localFreeV2.ts', import.meta.url), 'utf8');
const javascript = stripTypeScriptTypes(source, { mode: 'strip' });
const context = createContext({ Buffer, URL, URLSearchParams, TextEncoder, TextDecoder, Blob,
  AbortController, AbortSignal, setTimeout: (callback, ms) => setTimeout(callback, Math.min(ms, 5)), clearTimeout },
  { codeGeneration: { strings: false, wasm: false } });
const module = new SourceTextModule(javascript, { context, identifier: 'localFreeV2.ts' });
await module.link(() => { throw new Error('Imports are forbidden by the Toonflow media host'); });
await module.evaluate({ timeout: 1000 });
const provider = module.namespace.default;
assert.equal(provider.id, 'localFreeV2');
assert.equal(provider.rules.length, 0);
assert.deepEqual(Array.from(provider.models, item => item.type), ['image', 'video']);
assert.equal(provider.models[1].audio, false);
assert.equal(provider.models[1].durationResolutionMap[0].resolution[0], '480x832');
assert.match(source, /export default\s*\{/);
assert.ok(!/\b(?:import|require)\s*(?:\(|["'])/.test(source));

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=', 'base64');
const mp4 = Buffer.from([0, 0, 0, 24, 102, 116, 121, 112, 105, 115, 111, 109, 0, 0, 0, 0]);
const frame = { type: 'base64', data: png.toString('base64'), mimeType: 'image/png' };
const imageRequest = { model: 'realvisxlLocal', prompt: '清晰人物肖像', ratio: '9:16', size: '1K' };
const videoRequest = { model: 'wan14bLocal', prompt: '轻轻转头', firstFrame: frame, duration: 2, mode: 'singleImage', ratio: '9:16', resolution: '480x832' };
let passed = 0;
async function test(label, fn) { await fn(); passed++; process.stdout.write(`PASS ${label}\n`); }
function harness(kind, responseStates = ['succeeded']) {
  const calls = [];
  let index = 0;
  const fetch = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    assert.equal(init.redirect, 'error');
    assert.ok(init.signal instanceof AbortSignal);
    if (String(url).endsWith('/asset')) return new Response(kind === 'image' ? png : mp4);
    return Response.json({ id: 'job_123', status: responseStates[Math.min(index++, responseStates.length - 1)], kind, asset_url: '/jobs/job_123/asset' });
  };
  return { calls, self: { tool: { fetch } } };
}
await test('native TypeScript stripping and host-like VM execution', async () => {
  assert.equal(typeof provider.generateImage, 'function');
  assert.equal(typeof provider.generateVideo, 'function');
});
await test('image endpoint, fixed origin, exact field mapping, PNG binary output', async () => {
  const h = harness('image');
  const result = await provider.generateImage.call(h.self, { ...imageRequest, other: { seed: 42, negative_prompt: '模糊' } });
  assert.equal(h.calls[0].url, 'http://127.0.0.1:18766/jobs/image');
  assert.deepEqual(JSON.parse(h.calls[0].init.body), { prompt: '清晰人物肖像', aspect_ratio: '9:16', seed: 42, negative_prompt: '模糊' });
  assert.equal(result[0].mimeType, 'image/png');
  assert.equal(result[0].type, 'binary');
  assert.deepEqual(Buffer.from(result[0].data), png);
});
await test('video base64 first frame, asynchronous polling, MP4 binary output', async () => {
  const h = harness('video', ['queued', 'running', 'succeeded']);
  const result = await provider.generateVideo.call(h.self, videoRequest);
  const body = JSON.parse(h.calls[0].init.body);
  assert.equal(body.image, `data:image/png;base64,${png.toString('base64')}`);
  assert.equal(body.duration, 2);
  assert.equal(h.calls.filter(call => call.url.endsWith('/jobs/job_123')).length, 2);
  assert.equal(result[0].mediaType, 'video');
  assert.equal(result[0].mimeType, 'video/mp4');
});
await test('binary input works across VM realms', async () => {
  const h = harness('video');
  await provider.generateVideo.call(h.self, { ...videoRequest, firstFrame: { type: 'binary', data: new Uint8Array(png), mimeType: 'image/png' } });
});
await test('allowed loopback reference URL is fetched without redirects', async () => {
  const h = harness('video');
  const fetch = h.self.tool.fetch;
  h.self.tool.fetch = async (url, init) => String(url) === 'http://127.0.0.1:3000/a.png' ? (assert.equal(init.redirect, 'error'), new Response(png)) : fetch(url, init);
  await provider.generateVideo.call(h.self, { ...videoRequest, firstFrame: { type: 'url', url: 'http://127.0.0.1:3000/a.png' } });
  await provider.generateVideo.call(h.self, { ...videoRequest, firstFrame: { type: 'url', url: 'http://localhost:3000/a.png' } });
});
await test('unsupported fields never submit a generation job', async () => {
  const cases = [
    ['generateImage', { ...imageRequest, images: [frame] }],
    ['generateImage', { ...imageRequest, n: 2 }],
    ['generateImage', { ...imageRequest, ratio: '3:2' }],
    ['generateImage', { ...imageRequest, size: '4K' }],
    ['generateImage', { ...imageRequest, other: { baseUrl: 'https://example.com' } }],
    ['generateImage', { ...imageRequest, other: { negative_prompt: 'x'.repeat(8001) } }],
    ['generateVideo', { ...videoRequest, lastFrame: frame }],
    ['generateVideo', { ...videoRequest, images: [frame] }],
    ['generateVideo', { ...videoRequest, generateAudio: true }],
    ['generateVideo', { ...videoRequest, duration: 5 }],
    ['generateVideo', { ...videoRequest, resolution: '1080p' }],
    ['generateVideo', { ...videoRequest, mode: 'text' }],
    ['generateVideo', { ...videoRequest, other: { negative_prompt: 'unsupported' } }],
  ];
  for (const [method, request] of cases) {
    let calls = 0;
    await assert.rejects(provider[method].call({ tool: { fetch: async () => { calls++; throw new Error('Unexpected fetch'); } } }, request));
    assert.equal(calls, 0);
  }
});
await test('remote URLs, alternate ports, credentials and invalid images are rejected before job submission', async () => {
  for (const url of ['https://example.com/a.png', 'http://127.0.0.1:8188/a.png', 'http://user:pass@localhost:3000/a.png', 'file:///C:/image.png']) {
    let calls = 0;
    await assert.rejects(provider.generateVideo.call({ tool: { fetch: async () => { calls++; } } }, { ...videoRequest, firstFrame: { type: 'url', url } }));
    assert.equal(calls, 0);
  }
  await assert.rejects(provider.generateVideo.call(harness('video').self, { ...videoRequest, firstFrame: { type: 'base64', data: 'bad!', mimeType: 'image/png' } }), /Base64/);
  await assert.rejects(provider.generateVideo.call(harness('video').self, { ...videoRequest, firstFrame: { ...frame, mimeType: 'image/jpeg' } }), /MIME/);
  await assert.rejects(provider.generateVideo.call(harness('video').self, { ...videoRequest,
    firstFrame: { type: 'binary', data: new Uint8Array(12 * 1024 * 1024 + 1), mimeType: 'image/png' } }), /12 MiB/);
  await assert.rejects(provider.generateVideo.call(harness('video').self, { ...videoRequest,
    firstFrame: { type: 'base64', data: 'A'.repeat(16 * 1024 * 1024 + 101), mimeType: 'image/png' } }), /大小/);
});
await test('foreign result URLs and invalid result bytes are not accepted', async () => {
  const fake = { tool: { fetch: async () => Response.json({ id: 'job_123', status: 'succeeded', asset_url: 'https://example.com/video.mp4' }) } };
  await assert.rejects(provider.generateImage.call(fake, imageRequest), /本次任务/);
  const h = harness('video');
  const fetch = h.self.tool.fetch;
  h.self.tool.fetch = async (url, init) => String(url).endsWith('/asset') ? new Response('not an MP4') : fetch(url, init);
  await assert.rejects(provider.generateVideo.call(h.self, videoRequest), /MP4/);
});
await test('mismatched task IDs and unknown states cannot complete another task', async () => {
  let calls = 0;
  const mismatch = { tool: { fetch: async () => Response.json({ id: ++calls === 1 ? 'job_123' : 'other_job', status: calls === 1 ? 'queued' : 'succeeded', asset_url: '/jobs/other_job/asset' }) } };
  await assert.rejects(provider.generateImage.call(mismatch, imageRequest), /任务 ID/);
  const unknown = { tool: { fetch: async () => Response.json({ id: 'job_123', status: 'complete' }) } };
  await assert.rejects(provider.generateImage.call(unknown, imageRequest), /未知任务状态/);
});
await test('HTTP failures and oversized assets fail without automatic resubmission', async () => {
  let submissions = 0;
  const error = { tool: { fetch: async () => { submissions++; return Response.json({ detail: 'GPU unavailable' }, { status: 503 }); } } };
  await assert.rejects(provider.generateImage.call(error, imageRequest), /503.*GPU unavailable/);
  assert.equal(submissions, 1);
  const h = harness('image');
  const fetch = h.self.tool.fetch;
  h.self.tool.fetch = async (url, init) => String(url).endsWith('/asset')
    ? new Response(png, { headers: { 'content-length': String(33 * 1024 * 1024) } }) : fetch(url, init);
  await assert.rejects(provider.generateImage.call(h.self, imageRequest), /大小限制/);
});
await test('failed and needs-attention states surface errors and do not download', async () => {
  for (const state of ['failed', 'needs_attention']) {
    const h = harness('video', [state]);
    await assert.rejects(provider.generateVideo.call(h.self, videoRequest), /job_123/);
    assert.equal(h.calls.length, 1);
  }
});
await test('aborting a wait never interrupts the shared GPU queue', async () => {
  const h = harness('image', ['queued']);
  const abort = new AbortController();
  const waiting = provider.generateImage.call({ ...h.self, signal: abort.signal }, imageRequest);
  setTimeout(() => abort.abort(), 1);
  await assert.rejects(waiting, /可能仍在运行/);
  assert.ok(h.calls.every(call => !call.url.includes('interrupt') && !call.url.includes('cancel')));
});
await test('an already-cancelled request never submits a job', async () => {
  const abort = new AbortController(); abort.abort();
  const h = harness('image');
  await assert.rejects(provider.generateImage.call({ ...h.self, signal: abort.signal }, imageRequest));
  assert.equal(h.calls.length, 0);
});
process.stdout.write(`Validated ${passed} provider contracts with Node ${process.version}; this is protocol/VM validation, not a real GPU generation.\n`);
