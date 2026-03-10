/**
 * Next.js Instrumentation — runs once when the server starts.
 * Pre-warms caches for discover, flow analysis, and scanner so pages load with fresh data.
 * Skips a task if its cache file is less than 10 minutes old.
 */

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { registerNode } = await import("./lib/instrumentation-node");
    await registerNode();
  }
}
