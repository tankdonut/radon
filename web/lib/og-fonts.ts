import { readFile } from "fs/promises";
import { join } from "path";

let fontRegular: Buffer | null = null;
let fontBold: Buffer | null = null;

export async function loadFonts() {
  if (!fontRegular) {
    const dir = join(process.cwd(), "public", "fonts");
    fontRegular = await readFile(join(dir, "IBMPlexMono-Regular.ttf"));
    fontBold = await readFile(join(dir, "IBMPlexMono-Bold.ttf"));
  }
  return [
    {
      name: "IBM Plex Mono",
      data: fontRegular,
      weight: 400 as const,
      style: "normal" as const,
    },
    {
      name: "IBM Plex Mono",
      data: fontBold,
      weight: 700 as const,
      style: "normal" as const,
    },
  ];
}
