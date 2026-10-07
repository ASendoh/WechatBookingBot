"use strict";

const crypto = require("node:crypto");
const cloudbase = require("@cloudbase/node-sdk");
const app = cloudbase.init({ env: cloudbase.SYMBOL_DEFAULT_ENV });
const devices = app.database().collection("booking_devices");
// 上传新版 EXE 后，只需在云函数配置中填写这三个环境变量。
const RELEASE = {
  version: process.env.BOOKING_RELEASE_VERSION || "",
  fileID: process.env.BOOKING_RELEASE_FILE_ID || "",
  sha256: process.env.BOOKING_RELEASE_SHA256 || "",
};

function reply(statusCode, allowed, reason, update) {
  return {
    statusCode,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    body: JSON.stringify({ allowed, reason, ...(update ? { update } : {}) }),
  };
}

async function requiredUpdate(version) {
  if (!RELEASE.version && !RELEASE.fileID && !RELEASE.sha256) return null;
  if (!/^\d+\.\d+(?:\.\d+)?$/.test(RELEASE.version) ||
      !/^cloud:\/\//.test(RELEASE.fileID) ||
      !/^[0-9a-f]{64}$/i.test(RELEASE.sha256)) throw new Error("更新配置无效");
  const parts = (value) => /^\d+\.\d+(?:\.\d+)?$/.test(value || "")
    ? [...value.split(".").map(Number), 0].slice(0, 3) : [0, 0, 0];
  const current = parts(version);
  const latest = parts(RELEASE.version);
  if (!latest.some((part, index) => part > current[index] &&
      latest.slice(0, index).every((earlier, i) => earlier === current[i]))) return null;
  const result = await app.getTempFileURL({
    fileList: [{ fileID: RELEASE.fileID, maxAge: 3600 }],
  });
  const url = result.fileList?.[0]?.tempFileURL;
  if (typeof url !== "string" || !url.startsWith("https://")) {
    throw new Error("无法生成新版下载地址");
  }
  // 旧版客户端只接受三段版本号；过渡期仅对旧版补上末尾的 .0。
  const versionForClient = /^\d+\.\d+\.\d+$/.test(version || "") &&
    /^\d+\.\d+$/.test(RELEASE.version) ? `${RELEASE.version}.0` : RELEASE.version;
  return { version: versionForClient, url, sha256: RELEASE.sha256 };
}

exports.main = async (event) => {
  if (event.httpMethod !== "POST") return reply(405, false, "仅接受 POST");
  let input;
  try {
    const body = event.isBase64Encoded
      ? Buffer.from(event.body, "base64").toString("utf8") : event.body;
    if (!body || body.length > 2048) return reply(400, false, "请求体无效");
    input = JSON.parse(body);
  } catch (_) {
    return reply(400, false, "JSON 无效");
  }
  if (!input || typeof input !== "object") return reply(400, false, "设备信息无效");
  const { id, secret, computer, state, version, plan } = input;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id || "") ||
      !/^[0-9a-f]{64}$/i.test(secret || "") ||
      typeof computer !== "string" || computer.length > 100 ||
      (version !== undefined && (typeof version !== "string" || version.length > 30)) ||
      !["idle", "booking"].includes(state) ||
      (plan !== undefined && (
        !plan || typeof plan !== "object" ||
        !Number.isInteger(plan.court) || plan.court < 1 || plan.court > 17 ||
        !["19:00-21:00", "仅19:00-20:00", "仅20:00-21:00",
          "10:30-12:30", "仅10:30-11:30", "仅11:30-12:30"].includes(plan.time_mode)
      ))) {
    return reply(400, false, "设备信息无效");
  }
  const planFields = plan
    ? { planned_court: plan.court, planned_time_mode: plan.time_mode }
    : state === "idle" ? { planned_court: null, planned_time_mode: null } : {};

  const secretHash = crypto.createHash("sha256").update(secret, "hex").digest("hex");
  const doc = devices.doc(id);
  const now = new Date().toISOString();
  const ip = app.auth().getClientIP() || event.requestContext?.sourceIp || "";
  try {
    const existing = (await doc.get()).data[0];
    if (!existing) {
      await doc.set({
        secret_hash: secretHash, enabled: true, computer,
        ip, state, first_seen: now, last_seen: now, ...planFields,
      });
    } else {
      const stored = Buffer.from(existing.secret_hash || "", "hex");
      const received = Buffer.from(secretHash, "hex");
      if (stored.length !== received.length || !crypto.timingSafeEqual(stored, received)) {
        return reply(403, false, "设备凭据不匹配");
      }
      await doc.update({ computer, ip, state, last_seen: now, ...planFields });
      if (existing.enabled !== true) return reply(200, false, "设备已被管理员禁用");
    }
    const update = await requiredUpdate(version);
    return update
      ? reply(200, false, "必须安装新版", update)
      : reply(200, true, "已授权");
  } catch (error) {
    console.error("license check failed", error);
    return reply(503, false, "许可服务暂不可用");
  }
};
