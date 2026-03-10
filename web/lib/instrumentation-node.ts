/**
 * Node.js-only logic for Next.js Instrumentation.
 * Handles pre-warming caches for discover, flow analysis, and scanner.
 */

const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

async function isCacheFresh(filePath: string): Promise<boolean> {
  try {
    const { stat } = await import("fs/promises");
    const s = await stat(filePath);
    return Date.now() - s.mtimeMs < CACHE_TTL_MS;
  } catch {
    return false;
  }
}

export async function registerNode() {
  const { spawn } = await import("child_process");
  const { join } = await import("path");
  const { writeFile } = await import("fs/promises");

  const scriptsDir = join(process.cwd(), "..", "scripts");
  const dataDir = join(process.cwd(), "..", "data");

  type WarmTask = {
    name: string;
    script: string;
    args: string[];
    cachePath: string;
    logKey: string;
  };

  const tasks: WarmTask[] = [
    {
      name: "discover",
      script: "discover.py",
      args: ["--min-alerts", "1"],
      cachePath: join(dataDir, "discover.json"),
      logKey: "candidates_found",
    },
    {
      name: "flow analysis",
      script: "flow_analysis.py",
      args: [],
      cachePath: join(dataDir, "flow_analysis.json"),
      logKey: "positions_scanned",
    },
    {
      name: "scanner",
      script: "scanner.py",
      args: ["--top", "25"],
      cachePath: join(dataDir, "scanner.json"),
      logKey: "signals_found",
    },
  ];

  for (const task of tasks) {
    if (await isCacheFresh(task.cachePath)) {
      console.log(`[instrumentation] ${task.name} cache is fresh — skipping`);
      continue;
    }

    console.log(`[instrumentation] Pre-warming ${task.name} cache...`);

    const proc = spawn("python3", [task.script, ...task.args], {
      cwd: scriptsDir,
      env: { ...process.env },
    });

    let stdout = "";
    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", () => { /* progress to stderr — ignore */ });

    proc.on("close", async (code) => {
      if (code !== 0) {
        console.log(`[instrumentation] ${task.script} failed (exit code ${code})`);
        return;
      }
      try {
        const jsonStart = stdout.indexOf("{");
        if (jsonStart === -1) return;
        const data = JSON.parse(stdout.slice(jsonStart));
        if (data.error) {
          console.log(`[instrumentation] ${task.name} script returned error: ${data.error} — NOT overwriting cache`);
          return;
        }
        await writeFile(task.cachePath, JSON.stringify(data, null, 2));
        const count = data[task.logKey] ?? "?";
        console.log(`[instrumentation] ${task.name} cache warmed: ${count} ${task.logKey}`);
      } catch (err) {
        console.log(`[instrumentation] Failed to parse ${task.script} output:`, err);
      }
    });
  }
}
