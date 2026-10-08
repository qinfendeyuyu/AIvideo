/**
 * Toonflow vendor: local Wan2.1 I2V via ai-comic-drama adapter
 * @version 1.0
 *
 * Drop this file into Toonflow's vendor directory (or import via vendor UI),
 * then set:
 *   baseUrl = http://127.0.0.1:18765
 *   apiKey  = local-wan
 *
 * Requires:
 *   1) ComfyUI Wan14B stack running (see `logs/comfy_wan14b_photoreal.process.json` for the port; default fallback 8488 because Windows often excludes 8188)
 *   2) scripts/start_toonflow_local_wan_adapter.ps1
 */
type VideoMode =
  | "singleImage"
  | "startEndRequired"
  | "endFrameOptional"
  | "startFrameOptional"
  | "text"
  | (`videoReference:${number}` | `imageReference:${number}` | `audioReference:${number}`)[];
interface TextModel {
  name: string;
  modelName: string;
  type: "text";
  think: boolean;
}
interface ImageModel {
  name: string;
  modelName: string;
  type: "image";
  mode: ("text" | "singleImage" | "multiReference")[];
  associationSkills?: string;
}
interface VideoModel {
  name: string;
  modelName: string;
  type: "video";
  mode: VideoMode[];
  associationSkills?: string;
  audio: "optional" | false | true;
  durationResolutionMap: { duration: number[]; resolution: string[] }[];
}
interface TTSModel {
  name: string;
  modelName: string;
  type: "tts";
  voices: { title: string; voice: string }[];
}
interface VendorConfig {
  id: string;
  version: string;
  name: string;
  author: string;
  description?: string;
  icon?: string;
  inputs: { key: string; label: string; type: "text" | "password" | "url"; required: boolean; placeholder?: string }[];
  inputValues: Record<string, string>;
  models: (TextModel | ImageModel | VideoModel | TTSModel)[];
}
type ReferenceList =
  | { type: "image"; sourceType: "base64"; base64: string }
  | { type: "audio"; sourceType: "base64"; base64: string }
  | { type: "video"; sourceType: "base64"; base64: string };
interface ImageConfig {
  prompt: string;
  referenceList?: Extract<ReferenceList, { type: "image" }>[];
  size: "1K" | "2K" | "4K";
  aspectRatio: `${number}:${number}`;
}
interface VideoConfig {
  duration: number;
  resolution: string;
  aspectRatio: "16:9" | "9:16";
  prompt: string;
  referenceList?: ReferenceList[];
  audio?: boolean;
  mode: VideoMode[];
}
interface TTSConfig {
  text: string;
  voice: string;
  speechRate: number;
  pitchRate: number;
  volume: number;
  referenceList?: Extract<ReferenceList, { type: "audio" }>[];
}
interface PollResult {
  completed: boolean;
  data?: string;
  error?: string;
}
declare const axios: any;
declare const logger: (msg: string) => void;
declare const jsonwebtoken: any;
declare const zipImage: (base64: string, size: number) => Promise<string>;
declare const zipImageResolution: (base64: string, w: number, h: number) => Promise<string>;
declare const mergeImages: (base64Arr: string[], maxSize?: string) => Promise<string>;
declare const urlToBase64: (url: string) => Promise<string>;
declare const pollTask: (fn: () => Promise<PollResult>, interval?: number, timeout?: number) => Promise<PollResult>;
declare const createOpenAI: any;
declare const createDeepSeek: any;
declare const createZhipu: any;
declare const createQwen: any;
declare const createAnthropic: any;
declare const createOpenAICompatible: any;
declare const createXai: any;
declare const createMinimax: any;
declare const createGoogleGenerativeAI: any;
declare const exports: {
  vendor: VendorConfig;
  textRequest: (m: TextModel, t: boolean, tl: 0 | 1 | 2 | 3) => any;
  imageRequest: (c: ImageConfig, m: ImageModel) => Promise<string>;
  videoRequest: (c: VideoConfig, m: VideoModel) => Promise<string>;
  ttsRequest: (c: TTSConfig, m: TTSModel) => Promise<string>;
  checkForUpdates?: () => Promise<{ hasUpdate: boolean; latestVersion: string; notice: string }>;
  updateVendor?: () => Promise<string>;
};

const vendor: VendorConfig = {
  id: "localWanComfy",
  version: "1.0",
  author: "ai-comic-drama",
  name: "本地 Wan14B (Comfy)",
  description:
    "## 本地免费视频节点\n\n把 Toonflow 的图生视频打到本机 ComfyUI Wan2.1 I2V 14B FP8。\n\n**前置**：\n1. `start_comfy_wan14b.ps1` 已在 `8188` 就绪\n2. `start_toonflow_local_wan_adapter.ps1` 已在 `18765` 监听\n\n**注意**：现金≈¥0，但单镜通常 10–40 分钟；竖屏固定 480×832 / 8fps。",
  inputs: [
    { key: "apiKey", label: "API密钥", type: "password", required: true, placeholder: "local-wan" },
    {
      key: "baseUrl",
      label: "请求地址",
      type: "url",
      required: true,
      placeholder: "http://127.0.0.1:18765",
    },
  ],
  inputValues: {
    apiKey: "local-wan",
    baseUrl: "http://127.0.0.1:18765",
  },
  models: [
    {
      name: "Wan2.1 I2V 14B 本地",
      modelName: "wan2.1-i2v-14b-local",
      type: "video",
      mode: ["singleImage"],
      audio: false,
      durationResolutionMap: [
        { duration: [2, 3, 4], resolution: ["480p"] },
      ],
    },
  ],
};

const textRequest = (model: TextModel, think: boolean, thinkLevel: 0 | 1 | 2 | 3) => {
  throw new Error("本供应商仅提供本地视频；请另配 Ollama/DeepSeek 等文本模型");
};

const imageRequest = async (config: ImageConfig, model: ImageModel): Promise<string> => {
  throw new Error("本供应商仅提供本地视频；请另配本地 SD / 云图模型");
};

const videoRequest = async (config: VideoConfig, model: VideoModel): Promise<string> => {
  if (!vendor.inputValues.apiKey) throw new Error("缺少API Key");
  const apiKey = vendor.inputValues.apiKey.replace(/^Bearer\s+/i, "");
  const baseUrl = vendor.inputValues.baseUrl.replace(/\/$/, "");
  const imageRefs = (config.referenceList ?? []).filter((r) => r.type === "image").map((r) => r.base64);
  if (!imageRefs.length) throw new Error("本地 Wan I2V 需要单张首帧参考图");

  const body = {
    model: model.modelName,
    prompt: config.prompt,
    duration: config.duration,
    resolution: config.resolution || "480p",
    images: imageRefs,
    metadata: {
      img_url: imageRefs[0],
      aspectRatio: config.aspectRatio,
      timeout_minutes: 120,
    },
  };
  logger(`[localWanComfy] submit ${model.modelName} duration=${config.duration}`);
  const response = await fetch(`${baseUrl}/video/generateVideo`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`请求失败，状态码: ${response.status}, 错误信息: ${errorText}`);
  }
  const data = await response.json();
  const taskId = data.data;
  logger(`[localWanComfy] taskId=${taskId}`);

  const res = await pollTask(
    async () => {
      const queryResponse = await fetch(`${baseUrl}/video/getVideoStatus`, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ taskICode: taskId }),
      });
      if (!queryResponse.ok) {
        const errorText = await queryResponse.text();
        throw new Error(`轮询失败，状态码: ${queryResponse.status}, 错误信息: ${errorText}`);
      }
      const queryData = await queryResponse.json();
      const status = queryData?.status ?? queryData?.data?.status;
      switch (status) {
        case "completed":
        case "SUCCESS":
        case "success":
          return { completed: true, data: queryData.data.data };
        case "FAILURE":
        case "failed":
          return { completed: true, error: queryData?.data?.failReason ?? "视频生成失败" };
        default:
          return { completed: false };
      }
    },
    5000,
    7_200_000,
  );
  if (res.error) throw new Error(res.error);
  if (!res.data) throw new Error("空视频结果");
  return res.data;
};

const ttsRequest = async (config: TTSConfig, model: TTSModel): Promise<string> => {
  throw new Error("本供应商不提供 TTS");
};

const checkForUpdates = async (): Promise<{ hasUpdate: boolean; latestVersion: string; notice: string }> => {
  return { hasUpdate: false, latestVersion: "1.0", notice: "" };
};

const updateVendor = async (): Promise<string> => {
  return "";
};

exports.vendor = vendor;
exports.textRequest = textRequest;
exports.imageRequest = imageRequest;
exports.videoRequest = videoRequest;
exports.ttsRequest = ttsRequest;
exports.checkForUpdates = checkForUpdates;
exports.updateVendor = updateVendor;
export {};
