import { runScript, type ScriptResult } from "../runner";

export interface VCGInput {
  proxy?: string;
  backtest?: boolean;
  days?: number;
}

export interface VCGSignal {
  vcg: number | null;
  vcg_div: number | null;
  residual: number | null;
  beta1_vvix: number | null;
  beta2_vix: number | null;
  alpha: number | null;
  vix: number;
  vvix: number;
  credit_price: number;
  credit_5d_return_pct: number;
  hdr: number;
  hdr_conditions: {
    vvix_gt_110: boolean;
    credit_5d_gt_neg05pct: boolean;
    vix_lt_40: boolean;
  };
  ro: number;
  sign_ok: boolean;
  sign_suppressed: boolean;
  pi_panic: number;
  regime: string;
  interpretation: string;
  attribution: {
    vvix_pct: number;
    vix_pct: number;
    vvix_component: number;
    vix_component: number;
    model_implied: number;
  };
}

export interface VCGOutput {
  scan_time: string;
  market_open: boolean;
  credit_proxy: string;
  signal: VCGSignal;
  history: Array<{
    date: string;
    residual: number | null;
    vcg: number | null;
    vcg_div: number | null;
    beta1: number | null;
    beta2: number | null;
    vix: number;
    vvix: number;
    credit: number;
  }>;
}

export async function vcgScan(
  input: VCGInput = {},
): Promise<ScriptResult<VCGOutput>> {
  const args: string[] = ["--json"];

  if (input.proxy) {
    args.push("--proxy", input.proxy);
  }
  if (input.backtest) {
    args.push("--backtest");
    if (input.days) {
      args.push("--days", String(input.days));
    }
  }

  return runScript("scripts/vcg_scan.py", {
    args,
    timeout: 60_000,
  }) as Promise<ScriptResult<VCGOutput>>;
}
