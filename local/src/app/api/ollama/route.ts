import { NextRequest, NextResponse } from "next/server";

const OLLAMA = process.env.OLLAMA_URL || "http://127.0.0.1:11434";

export async function GET() {
  try {
    const r = await fetch(`${OLLAMA}/api/tags`, { cache: "no-store" });
    if (!r.ok) return NextResponse.json({ status: "offline" });
    const data = await r.json();
    return NextResponse.json({
      status: "idle",
      models: (data.models || []).map((m: { name: string }) => m.name),
    });
  } catch {
    return NextResponse.json({ status: "offline", models: [] });
  }
}

export async function POST(req: NextRequest) {
  const job = await req.json();
  const model = job.model || "llama3.2";
  const prompt = buildPrompt(job);
  try {
    const r = await fetch(`${OLLAMA}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, prompt, stream: false, format: "json" }),
    });
    if (!r.ok) {
      return NextResponse.json({
        id: job.id,
        kind: job.kind,
        ok: false,
        payload: { error: await r.text() },
      });
    }
    const data = await r.json();
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(data.response || "{}");
    } catch {
      parsed = { raw: data.response };
    }
    return NextResponse.json({
      id: job.id,
      kind: job.kind,
      ok: true,
      payload: { ...job.payload, ...parsed },
    });
  } catch (e) {
    return NextResponse.json({
      id: job.id,
      kind: job.kind,
      ok: false,
      payload: { error: String(e) },
    });
  }
}

function buildPrompt(job: { kind: string; payload: Record<string, unknown> }) {
  if (job.kind === "questionnaire") {
    return `Определи, является ли сообщение анкетой новичка в закрытом чате (кто он, чем занимается, зачем пришёл). Ответь JSON: {"is_questionnaire": true/false}\nСообщение: ${job.payload.text}`;
  }
  if (job.kind === "profanity") {
    return `Есть ли в тексте мат или оскорбления на русском? JSON: {"is_profanity": true/false}\nТекст: ${job.payload.text}`;
  }
  if (job.kind === "term") {
    const glossary = JSON.stringify(job.payload.glossary || {}).slice(0, 8000);
    return `Вопрос по терминологии. Если термин есть в базе — ответь кратко по базе. Если нет — {"answer": null}. JSON: {"answer": "..." или null}\nБаза: ${glossary}\nВопрос: ${job.payload.query}`;
  }
  if (job.kind === "schedule") {
    return `Извлеки активность из фразы «запланировать ...». JSON: {"title": str, "when": unix_timestamp_seconds} или {"title": null}\nСейчас unix: ${Math.floor(Date.now() / 1000)}\nТекст: ${job.payload.text}`;
  }
  return `JSON: {}\n${JSON.stringify(job)}`;
}
