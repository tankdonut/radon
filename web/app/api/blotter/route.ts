import { NextResponse } from "next/server";
import { readFile, writeFile } from "fs/promises";
import { join } from "path";
import { spawn } from "child_process";

export const runtime = "nodejs";

const BLOTTER_CACHE_PATH = join(process.cwd(), "..", "data", "blotter.json");
const SCRIPTS_DIR = join(process.cwd(), "..", "scripts");

function runFlexQuery(): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", ["-m", "trade_blotter.flex_query", "--json"], {
      cwd: SCRIPTS_DIR,
      timeout: 120_000,
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });
    proc.on("close", (code) => {
      if (code !== 0) reject(new Error(stderr || `flex_query.py exited with code ${code}`));
      else resolve(stdout);
    });
    proc.on("error", reject);
  });
}

export async function GET(): Promise<Response> {
  try {
    const raw = await readFile(BLOTTER_CACHE_PATH, "utf-8");
    const data = JSON.parse(raw);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({
      as_of: "",
      summary: { closed_trades: 0, open_trades: 0, total_commissions: 0, realized_pnl: 0 },
      closed_trades: [],
      open_trades: [],
    });
  }
}

export async function POST(): Promise<Response> {
  try {
    const stdout = await runFlexQuery();
    // Find JSON object in stdout (script may print progress lines before JSON)
    const jsonStart = stdout.indexOf("{");
    if (jsonStart === -1) throw new Error("No JSON output from flex_query.py");
    const jsonStr = stdout.slice(jsonStart);
    const data = JSON.parse(jsonStr);

    await writeFile(BLOTTER_CACHE_PATH, JSON.stringify(data, null, 2));

    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Blotter sync failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
