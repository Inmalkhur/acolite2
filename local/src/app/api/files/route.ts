import { NextRequest, NextResponse } from "next/server";
import { listMd, writeMd } from "@/lib/files";

export async function GET() {
  const files = await listMd();
  return NextResponse.json({ files });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const rel = String(body.path || "");
  const content = String(body.content || "");
  const append = Boolean(body.append);
  if (!rel.endsWith(".md") && !rel.endsWith(".json")) {
    return NextResponse.json({ error: "only md/json" }, { status: 400 });
  }
  await writeMd(rel, content, append);
  return NextResponse.json({ ok: true });
}
