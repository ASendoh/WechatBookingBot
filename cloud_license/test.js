"use strict";

const assert = require("node:assert/strict");
const Module = require("node:module");
const records = new Map();
const sdk = {
  SYMBOL_DEFAULT_ENV: "test",
  init: () => ({
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
  const event = (key) => ({ httpMethod: "POST", body: JSON.stringify({
    id, secret: key, computer: "test-pc", state: "booking",
  }) });
  const answer = async (request) => JSON.parse((await main(request)).body);
  assert.equal((await answer(event(secret))).allowed, true);
  assert.equal(records.get(id).enabled, true);
  assert.equal(records.get(id).ip, "203.0.113.1");
  assert.equal((await answer(event(secret))).allowed, true);
  assert.equal((await answer(event("cd".repeat(32)))).allowed, false);
  records.get(id).enabled = false;
  assert.equal((await answer(event(secret))).allowed, false);
  assert.equal((await answer({ httpMethod: "POST", body: "null" })).allowed, false);
  console.log("云端许可逻辑自检通过");
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
