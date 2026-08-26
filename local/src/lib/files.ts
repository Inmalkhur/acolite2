import { promises as fs } from "fs";
import path from "path";

export function dataRoot() {
  return process.env.DATA_DIR || path.join(process.cwd(), "..", "data");
}

export function safeJoin(rel: string) {
  const root = path.resolve(dataRoot());
  const full = path.resolve(root, rel);
  if (!full.startsWith(root)) throw new Error("bad path");
  return full;
}

export async function listMd(): Promise<{ path: string; content: string }[]> {
  const root = dataRoot();
  const out: { path: string; content: string }[] = [];
  async function walk(dir: string, prefix: string) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const rel = prefix ? `${prefix}/${e.name}` : e.name;
      const p = path.join(dir, e.name);
      if (e.isDirectory()) await walk(p, rel);
      else if (e.name.endsWith(".md")) {
        out.push({ path: rel, content: await fs.readFile(p, "utf8") });
      }
    }
  }
  await walk(root, "");
  return out;
}

export async function writeMd(rel: string, content: string, append = false) {
  const full = safeJoin(rel);
  await fs.mkdir(path.dirname(full), { recursive: true });
  if (append) await fs.appendFile(full, content.startsWith("\n") ? content : `\n${content}`, "utf8");
  else await fs.writeFile(full, content, "utf8");
}
