/** Toonflow 2.x provider. Reviewed against upstream 72a895c26aab3f54c5a914517615362208fa6008. */
type Source =
  | { type: "url"; url: string; mimeType?: string }
  | { type: "base64"; data: string; mimeType: string }
  | { type: "binary"; data: Uint8Array; mimeType: string };
type Context = { signal?: AbortSignal; tool: { fetch: typeof fetch } };
type Asset = { mediaType: "image" | "video"; type: "binary"; data: Uint8Array; mimeType: string };
type Request = {
  model: string; prompt: string; ratio?: string; size?: string; quality?: string;
  outputFormat?: string; n?: number; images?: Source[]; mask?: Source;
  firstFrame?: Source; lastFrame?: Source; videos?: Source[]; audios?: Source[];
  duration?: number; resolution?: string; generateAudio?: boolean; watermark?: boolean;
  mode?: string | string[]; other?: Record<string, unknown>;
};
type Job = { id: string; status: string; kind?: string; error?: unknown; asset_url?: string };

function check(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}
function message(error: unknown): string {
  if (typeof error === "string") return error.slice(0, 1000);
  if (error && typeof error === "object" && "message" in error) return String(error.message).slice(0, 1000);
  return "本地生成失败，请查看队列状态和 ComfyUI 日志";
}
function localUrl(value: string): URL {
  const url = new URL(value);
  check(url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
    && ["3000", "18766"].includes(url.port) && !url.username && !url.password && !url.hash,
  "参考图 URL 只能来自本机 Toonflow 3000 或免费网关 18766 端口");
  // Avoid even local hostname resolution: a hosts override must not send media off-device.
  if (url.hostname === "localhost") url.hostname = "127.0.0.1";
  return url;
}
function signalFor(context: Context, milliseconds: number): AbortSignal {
  return AbortSignal.any([AbortSignal.timeout(milliseconds), ...(context.signal ? [context.signal] : [])]);
}
async function fetchChecked(context: Context, url: string, init: RequestInit, signal: AbortSignal): Promise<Response> {
  signal.throwIfAborted();
  const response = await context.tool.fetch(url, { ...init, signal, redirect: "error" });
  if (!response.ok) {
    let detail = "";
    try { const data = await response.json(); detail = message(data.detail ?? data.error ?? data.message); } catch { /* No error body is required. */ }
    throw new Error(`本地服务 HTTP ${response.status}${detail ? "：" + detail : ""}`);
  }
  return response;
}
async function bytes(response: Response, limit: number, signal: AbortSignal): Promise<Uint8Array> {
  const length = response.headers.get("content-length");
  check(length === null || (Number.isFinite(Number(length)) && Number(length) <= limit), "媒体文件超过本地接入的大小限制");
  check(response.body, "本地服务返回了空媒体内容");
  const reader = response.body.getReader();
  const parts: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      signal.throwIfAborted();
      const part = await reader.read();
      if (part.done) break;
      size += part.value.byteLength;
      check(size <= limit, "媒体文件超过本地接入的大小限制");
      parts.push(part.value);
    }
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally { reader.releaseLock(); }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) { result.set(part, offset); offset += part.byteLength; }
  check(result.length > 0, "本地服务返回了空媒体文件");
  return result;
}
function imageMime(data: Uint8Array): string {
  if (data.length >= 8 && data[0] === 137 && data[1] === 80 && data[2] === 78 && data[3] === 71
    && data[4] === 13 && data[5] === 10 && data[6] === 26 && data[7] === 10) return "image/png";
  if (data.length >= 3 && data[0] === 255 && data[1] === 216 && data[2] === 255) return "image/jpeg";
  if (data.length >= 12 && Buffer.from(data.subarray(0, 4)).toString() === "RIFF"
    && Buffer.from(data.subarray(8, 12)).toString() === "WEBP") return "image/webp";
  throw new Error("首帧必须是实际 PNG、JPEG 或 WebP 图片，不能用扩展名冒充");
}
async function firstFrame(context: Context, source: Source, signal: AbortSignal): Promise<string> {
  check(source && typeof source === "object", "图生视频需要一张首帧图片");
  let data: Uint8Array;
  let declared = source.mimeType;
  if (source.type === "url") {
    const url = localUrl(source.url);
    data = await bytes(await fetchChecked(context, url.href, {}, AbortSignal.any([signal, AbortSignal.timeout(60000)])), 12 * 1024 * 1024, signal);
  } else if (source.type === "base64") {
    check(typeof source.data === "string" && source.data.length <= 16 * 1024 * 1024 + 100, "首帧 Base64 格式或大小无效");
    let encoded = source.data;
    if (encoded.startsWith("data:")) {
      const matched = /^data:(image\/(?:png|jpeg|webp));base64,(.*)$/s.exec(encoded);
      check(matched, "首帧 Data URL 格式无效");
      check(!declared || declared === matched[1], "首帧 MIME 声明互相冲突");
      declared = matched[1]; encoded = matched[2];
    }
    check(encoded.length > 0 && encoded.length % 4 === 0 && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded), "首帧 Base64 编码无效");
    data = new Uint8Array(Buffer.from(encoded, "base64"));
  } else if (source.type === "binary") {
    check(ArrayBuffer.isView(source.data) && source.data.BYTES_PER_ELEMENT === 1, "首帧二进制数据必须是 Uint8Array");
    data = new Uint8Array(source.data.buffer, source.data.byteOffset, source.data.byteLength);
  } else throw new Error("不支持的首帧媒体来源");
  check(data.byteLength > 0 && data.byteLength <= 12 * 1024 * 1024, "首帧图片必须介于 1 字节和 12 MiB 之间");
  const mime = imageMime(data);
  check(!declared || declared === mime, "首帧 MIME 与实际图片内容不一致");
  return `data:${mime};base64,${Buffer.from(data).toString("base64")}`;
}
function options(request: Request, allowNegative: boolean): Record<string, unknown> {
  const extra = request.other ?? {};
  check(extra && typeof extra === "object" && !Array.isArray(extra), "other 必须是参数对象");
  check(Object.keys(extra).every(key => key === "seed" || (allowNegative && key === "negative_prompt")), "不支持该扩展参数；地址、模型路径和工作流不能通过请求覆盖");
  if (extra.seed !== undefined) check(Number.isSafeInteger(extra.seed) && Number(extra.seed) >= 0, "seed 必须是非负安全整数");
  if (extra.negative_prompt !== undefined) check(typeof extra.negative_prompt === "string" && extra.negative_prompt.length <= 8000, "负面提示词必须是字符串且不能超过 8000 字");
  check(typeof request.prompt === "string" && request.prompt.trim().length > 0 && request.prompt.length <= 10000, "提示词不能为空或超过 10000 字");
  return extra;
}
function noReferences(request: Request, image: boolean): void {
  check(!request.images?.length && !request.mask && !request.lastFrame && !request.videos?.length && !request.audios?.length,
    image ? "本地图像模型目前只支持文生图，不支持参考图、蒙版或媒体编辑" : "本地视频只支持单张首帧，不支持额外参考图、尾帧、音频或视频参考");
}
function pause(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const finish = () => { clearTimeout(timer); signal.removeEventListener("abort", abort); };
    const abort = () => { finish(); reject(signal.reason); };
    const timer = setTimeout(() => { finish(); resolve(); }, 3000);
    signal.addEventListener("abort", abort, { once: true });
  });
}
function job(value: unknown, id?: string): Job {
  check(value && typeof value === "object", "网关没有返回有效任务信息");
  const data = value as Job;
  check(typeof data.id === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(data.id) && (!id || id === data.id), "网关任务 ID 无效或与本次任务不一致");
  check(["queued", "submitting", "running", "succeeded", "failed", "needs_attention"].includes(data.status), "网关返回了未知任务状态");
  return data;
}
async function run(context: Context, kind: "image" | "video", payload: Record<string, unknown>, signal: AbortSignal): Promise<Asset[]> {
  const base = "http://127.0.0.1:18766";
  const initial = await fetchChecked(context, `${base}/jobs/${kind}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }, AbortSignal.any([signal, AbortSignal.timeout(60000)]));
  let current = job(await initial.json());
  const id = current.id;
  try {
    while (true) {
      signal.throwIfAborted();
      check(!current.kind || current.kind === kind, "网关返回了错误的媒体任务类型");
      if (current.status === "failed") throw new Error(message(current.error));
      if (current.status === "needs_attention") throw new Error(`任务需要人工检查：${message(current.error)}`);
      if (current.status === "succeeded") break;
      await pause(signal);
      const response = await fetchChecked(context, `${base}/jobs/${id}`, {}, AbortSignal.any([signal, AbortSignal.timeout(30000)]));
      current = job(await response.json(), id);
    }
    check(current.asset_url === `/jobs/${id}/asset`, "任务没有返回本次任务的本地媒体地址");
    const response = await fetchChecked(context, `${base}${current.asset_url}`, {}, AbortSignal.any([signal, AbortSignal.timeout(180000)]));
    const data = await bytes(response, kind === "image" ? 12 * 1024 * 1024 : 256 * 1024 * 1024, signal);
    if (kind === "image") check(imageMime(data) === "image/png", "图片任务必须返回 PNG 文件");
    else check(data.length >= 12 && Buffer.from(data.subarray(4, 8)).toString() === "ftyp", "视频任务没有返回有效 MP4 文件头");
    signal.throwIfAborted();
    return [{ mediaType: kind, type: "binary", data, mimeType: kind === "image" ? "image/png" : "video/mp4" }];
  } catch (error) {
    if (signal.aborted) {
      const cancelled = new Error(`等待已结束；本地任务 ${id} 可能仍在运行，请先检查队列，避免重复提交。`);
      cancelled.name = "AbortError"; throw cancelled;
    }
    throw new Error(`任务 ${id}：${message(error)}`);
  }
}

export default {
  id: "localFreeV2",
  label: "本机免费 · RealVisXL / Wan 14B",
  version: "2.0.0",
  readme: "仅连接本机 127.0.0.1:18766 免费网关，无 API Key、无按次模型费。图片原生 720×1280、1280×720 或 1024×1024。视频原生 480×832、8fps、17/25/33 帧；9:16 为竖构图选项，原生比例约 15:26，并非精确 9:16 或高清。视频无音轨。2/3/4 秒为动作采样跨度，文件时长因首帧多 0.125 秒；成片需另行裁切/插帧。每次只运行一个 GPU 任务。最长等候 8 小时；关闭等待不会中断共享 ComfyUI，也不应立即重复提交。软件许可与模型、素材许可分别适用。",
  rules: [],
  models: [
    { id: "realvisxlLocal", label: "RealVisXL 本地文生图", type: "image", mode: ["text"], imageSizes: ["1K"], imageRatios: ["9:16", "16:9", "1:1"] },
    { id: "wan14bLocal", label: "Wan 14B 本地竖屏（480×832 / 8fps）", type: "video", mode: ["singleImage"], audio: false, durationResolutionMap: [{ duration: [2, 3, 4], resolution: ["480x832"] }] }
  ],
  async generateImage(this: Context, request: Request): Promise<Asset[]> {
    this.signal?.throwIfAborted();
    check(request.model === "realvisxlLocal", "请选择本地 RealVisXL 图像模型");
    noReferences(request, true);
    check(!request.firstFrame && request.duration === undefined && request.resolution === undefined && !request.generateAudio
      && request.watermark === undefined && (!request.mode || request.mode === "text"), "本地文生图不支持这些视频参数");
    check((request.n === undefined || request.n === 1) && (request.size === undefined || request.size === "1K")
      && request.quality === undefined && (request.outputFormat === undefined || request.outputFormat === "png"), "本地图像仅支持一次 1 张、1K 档、PNG 输出；采样质量由本机配置固定");
    const ratio = request.ratio ?? "9:16";
    check(["9:16", "16:9", "1:1"].includes(ratio), "图片只支持 9:16、16:9 或 1:1");
    const extra = options(request, true);
    return run(this, "image", { prompt: request.prompt.trim(), aspect_ratio: ratio, ...extra }, signalFor(this, 8 * 60 * 60 * 1000));
  },
  async generateVideo(this: Context, request: Request): Promise<Asset[]> {
    this.signal?.throwIfAborted();
    check(request.model === "wan14bLocal", "请选择本地 Wan 14B 视频模型");
    noReferences(request, false);
    check(request.firstFrame, "Wan 图生视频需要一张首帧图片");
    check(request.mode === undefined || request.mode === "singleImage", "本地 Wan 仅支持 singleImage 首帧模式");
    check(request.ratio === undefined || request.ratio === "9:16", "本地 Wan 当前只支持竖构图");
    check(request.resolution === undefined || request.resolution === "480x832", "原生视频只支持 480x832，不能宣称 720p 或 1080p");
    check(!request.generateAudio && !request.watermark && request.size === undefined && request.quality === undefined
      && request.outputFormat === undefined && request.n === undefined, "本地 Wan 不支持音轨、水印或这些图片参数");
    const duration = request.duration ?? 4;
    check([2, 3, 4].includes(duration), "本地 Wan 动作采样跨度只支持 2、3、4 秒");
    const extra = options(request, false);
    const signal = signalFor(this, 8 * 60 * 60 * 1000);
    const image = await firstFrame(this, request.firstFrame, signal);
    return run(this, "video", { prompt: request.prompt.trim(), image, duration, aspect_ratio: "9:16", ...extra }, signal);
  }
};
