import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createSyncMutex } from "../lib/syncMutex";

// =============================================================================
// Sync mutex — coalesces concurrent calls into a single execution
// =============================================================================

describe("createSyncMutex", () => {
  it("executes the function on first call", async () => {
    let callCount = 0;
    const mutex = createSyncMutex(async () => {
      callCount++;
      return { ok: true, stderr: "" };
    });

    const result = await mutex();
    assert.equal(callCount, 1);
    assert.equal(result.ok, true);
  });

  it("coalesces concurrent calls — runs fn only once", async () => {
    let callCount = 0;
    const mutex = createSyncMutex(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 50));
      return { ok: true, stderr: "" };
    });

    const [r1, r2, r3] = await Promise.all([mutex(), mutex(), mutex()]);
    assert.equal(callCount, 1, "should only execute fn once for concurrent calls");
    assert.equal(r1.ok, true);
    assert.equal(r2.ok, true);
    assert.equal(r3.ok, true);
  });

  it("allows a new call after the previous one finishes", async () => {
    let callCount = 0;
    const mutex = createSyncMutex(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 10));
      return { ok: true, stderr: `call-${callCount}` };
    });

    const r1 = await mutex();
    assert.equal(callCount, 1);
    assert.equal(r1.stderr, "call-1");

    const r2 = await mutex();
    assert.equal(callCount, 2, "should execute fn again after previous call finished");
    assert.equal(r2.stderr, "call-2");
  });

  it("propagates errors to all waiters and resets", async () => {
    let callCount = 0;
    const mutex = createSyncMutex(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 20));
      throw new Error("sync failed");
    });

    const results = await Promise.allSettled([mutex(), mutex()]);
    assert.equal(callCount, 1, "should only execute fn once even on error");
    assert.equal(results[0].status, "rejected");
    assert.equal(results[1].status, "rejected");
    assert.equal((results[0] as PromiseRejectedResult).reason.message, "sync failed");
    assert.equal((results[1] as PromiseRejectedResult).reason.message, "sync failed");

    // After error, mutex should be reset — new call should work
    callCount = 0;
    const mutex2 = createSyncMutex(async () => {
      callCount++;
      return { ok: true, stderr: "" };
    });
    const r = await mutex2();
    assert.equal(r.ok, true);
  });

  it("second wave of calls after first wave completes runs fn again", async () => {
    let callCount = 0;
    const mutex = createSyncMutex(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 20));
      return { ok: true, stderr: `wave-${callCount}` };
    });

    // Wave 1
    const [w1a, w1b] = await Promise.all([mutex(), mutex()]);
    assert.equal(callCount, 1);
    assert.equal(w1a.stderr, "wave-1");
    assert.equal(w1b.stderr, "wave-1");

    // Wave 2
    const [w2a, w2b] = await Promise.all([mutex(), mutex()]);
    assert.equal(callCount, 2, "second wave should trigger a new execution");
    assert.equal(w2a.stderr, "wave-2");
    assert.equal(w2b.stderr, "wave-2");
  });
});

// =============================================================================
// Route-level integration: routes use the mutex
// =============================================================================

describe("Orders routes use sync mutex", () => {
  it("orders route imports and uses createSyncMutex", async () => {
    const { readFile } = await import("node:fs/promises");
    const { resolve } = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const __dirname = resolve(fileURLToPath(import.meta.url), "..");

    const content = await readFile(resolve(__dirname, "../app/api/orders/route.ts"), "utf8");
    assert.ok(content.includes("syncMutex"), "orders route must use syncMutex");
    assert.ok(content.includes("createSyncMutex"), "orders route must import createSyncMutex");
  });

  it("cancel route imports and uses createSyncMutex", async () => {
    const { readFile } = await import("node:fs/promises");
    const { resolve } = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const __dirname = resolve(fileURLToPath(import.meta.url), "..");

    const content = await readFile(resolve(__dirname, "../app/api/orders/cancel/route.ts"), "utf8");
    assert.ok(content.includes("syncMutex"), "cancel route must use syncMutex");
    assert.ok(content.includes("createSyncMutex"), "cancel route must import createSyncMutex");
  });

  it("modify route imports and uses createSyncMutex", async () => {
    const { readFile } = await import("node:fs/promises");
    const { resolve } = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const __dirname = resolve(fileURLToPath(import.meta.url), "..");

    const content = await readFile(resolve(__dirname, "../app/api/orders/modify/route.ts"), "utf8");
    assert.ok(content.includes("syncMutex"), "modify route must use syncMutex");
    assert.ok(content.includes("createSyncMutex"), "modify route must import createSyncMutex");
  });
});
