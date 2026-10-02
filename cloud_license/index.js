"use strict";

const crypto = require("node:crypto");
const cloudbase = require("@cloudbase/node-sdk");
const app = cloudbase.init({ env: cloudbase.SYMBOL_DEFAULT_ENV });
const devices = app.database().collection("booking_devices");

function reply(statusCode, allowed, reason) {
  return {
    statusCode,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    body: JSON.stringify({ allowed, reason }),
  };
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
  const { id, secret, computer, state } = input;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id || "") ||
      !/^[0-9a-f]{64}$/i.test(secret || "") ||
      typeof computer !== "string" || computer.length > 100 ||
      !["idle", "booking"].includes(state)) {
    return reply(400, false, "设备信息无效");
  }

  const secretHash = crypto.createHash("sha256").update(secret, "hex").digest("hex");
  const doc = devices.doc(id);
  const now = new Date().toISOString();
  const ip = app.auth().getClientIP() || event.requestContext?.sourceIp || "";
  try {
    const existing = (await doc.get()).data[0];
    if (!existing) {
      await doc.set({
        secret_hash: secretHash, enabled: true, computer,
        ip, state, first_seen: now, last_seen: now,
      });
      return reply(200, true, "新设备已授权");
    }
    const stored = Buffer.from(existing.secret_hash || "", "hex");
    const received = Buffer.from(secretHash, "hex");
    if (stored.length !== received.length || !crypto.timingSafeEqual(stored, received)) {
      return reply(403, false, "设备凭据不匹配");
    }
    await doc.update({ computer, ip, state, last_seen: now });
    return reply(200, existing.enabled === true,
      existing.enabled === true ? "已授权" : "设备已被管理员禁用");
  } catch (error) {
    console.error("license check failed", error);
    return reply(503, false, "许可服务暂不可用");
  }
};
