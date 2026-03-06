/**
 * Next.js Instrumentation — runs once when the server starts.
 * Pre-warms caches for discover, flow analysis, and scanner so pages load with fresh data.
 * Journal reads trade_log.json directly (no script to run).
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
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
      console.log(`[instrumentation] Pre-warming ${task.name} cache...`);

      const proc = spawn("python3", [task.script, ...task.args], {
        cwd: scriptsDir,
        timeout: 120_000,
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
          await writeFile(task.cachePath, JSON.stringify(data, null, 2));
          const count = data[task.logKey] ?? "?";
          console.log(`[instrumentation] ${task.name} cache warmed: ${count} ${task.logKey}`);
        } catch (err) {
          console.log(`[instrumentation] Failed to parse ${task.script} output:`, err);
        }
      });
    }
  }
}
