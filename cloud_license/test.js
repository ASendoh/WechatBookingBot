"use strict";

const assert = require("node:assert/strict");
const Module = require("node:module");
process.env.BOOKING_RELEASE_VERSION = "2.0";
process.env.BOOKING_RELEASE_FILE_ID = "cloud://test/new.exe";
process.env.BOOKING_RELEASE_SHA256 = "ab".repeat(32);
const records = new Map();
let linkRequests = 0;
const sdk = {
  SYMBOL_DEFAULT_ENV: "test",
  init: () => ({
    getTempFileURL: async () => {
      linkRequests++;
      return { fileList: [{ tempFileURL: "https://example.invalid/new.exe" }] };
    },
    auth: () => ({ getClientIP: () => "203.0.113.1" }),
    database: () => ({ collection: () => ({ doc: (id) => ({
      get: async () => ({ data: records.has(id) ? [records.get(id)] : [] }),
      set: async (value) => records.set(id, value),
      update: async (value) => Object.assign(records.get(id), value),
    }) }) }),
  }),
};
const originalLoad = Module._load;
Module._load = function (name, parent, main) {
  return name === "@cloudbase/node-sdk" ? sdk : originalLoad(name, parent, main);
};
const { main } = require("./index");
Module._load = originalLoad;

async function run() {
  const id = "12345678-1234-1234-1234-123456789abc";
  const secret = "ab".repeat(32);
  const event = (key, version = "2.0") => ({ httpMethod: "POST", body: JSON.stringify({
    id, secret: key, computer: "test-pc", state: "booking", version,
  }) });
  const answer = async (request) => JSON.parse((await main(request)).body);
  assert.equal((await answer(event(secret))).allowed, true);
  assert.equal(records.get(id).enabled, true);
  assert.equal(records.get(id).ip, "203.0.113.1");
  const scheduled = JSON.parse(event(secret).body);
  scheduled.plan = { court: 17, time_mode: "10:30-12:30" };
  assert.equal((await answer({ httpMethod: "POST", body: JSON.stringify(scheduled) })).allowed, true);
  assert.equal(records.get(id).planned_court, 17);
  assert.equal(records.get(id).planned_time_mode, "10:30-12:30");
  assert.equal((await answer(event(secret, "2.0"))).allowed, true);
  assert.equal(records.get(id).planned_court, 17);
  const idle = JSON.parse(event(secret).body);
  idle.state = "idle";
  assert.equal((await answer({ httpMethod: "POST", body: JSON.stringify(idle) })).allowed, true);
  assert.equal(records.get(id).planned_court, null);
  assert.equal(records.get(id).planned_time_mode, null);
  scheduled.plan.court = 18;
  assert.equal((await answer({ httpMethod: "POST", body: JSON.stringify(scheduled) })).allowed, false);
  assert.equal((await answer(event(secret))).allowed, true);
  const old = await answer(event(secret, "1.1.1"));
  assert.equal(old.allowed, false);
  assert.equal(old.update.version, "2.0.0");
  assert.equal(old.update.url, "https://example.invalid/new.exe");
  assert.equal(old.update.sha256, "ab".repeat(32));
  assert.equal((await answer(event(secret, "2.1"))).allowed, true);
  const legacy = JSON.parse(event(secret).body);
  delete legacy.version;
  assert.equal((await answer({ httpMethod: "POST", body: JSON.stringify(legacy) })).allowed, false);
  assert.equal(linkRequests, 2);
  assert.equal((await answer(event("cd".repeat(32)))).allowed, false);
  records.get(id).enabled = false;
  assert.equal((await answer(event(secret))).allowed, false);
  assert.equal((await answer({ httpMethod: "POST", body: "null" })).allowed, false);
  console.log("云端许可逻辑自检通过");
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
