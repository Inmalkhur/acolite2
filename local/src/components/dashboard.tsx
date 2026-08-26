"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge, Card, Input, Label, Textarea } from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BotConfig, defaultConfig, NlpJob } from "@/lib/types";

type FileRow = { path: string; content: string };
type OllamaStatus = "offline" | "idle" | "busy";

export function Dashboard() {
  const [serverUrl, setServerUrl] = useState("http://127.0.0.1:43121");
  const [secret, setSecret] = useState("change-me");
  const [connected, setConnected] = useState(false);
  const [config, setConfig] = useState<BotConfig>(defaultConfig);
  const [jobs, setJobs] = useState<NlpJob[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [files, setFiles] = useState<FileRow[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [editor, setEditor] = useState("");
  const [ollama, setOllama] = useState<OllamaStatus>("offline");
  const [models, setModels] = useState<string[]>([]);
  const [saveMsg, setSaveMsg] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const flushTimer = useRef<number | null>(null);

  const headers = useMemo(
    () => ({ "Content-Type": "application/json", "X-Sync-Secret": secret }),
    [secret]
  );

  const selectedFile = files.find((f) => f.path === selected);

  const reloadFiles = useCallback(async () => {
    const r = await fetch("/api/files");
    const data = await r.json();
    setFiles(data.files || []);
  }, []);

  const pingOllama = useCallback(async () => {
    const r = await fetch("/api/ollama");
    const data = await r.json();
    setOllama(data.status === "idle" ? "idle" : "offline");
    setModels(data.models || []);
  }, []);

  const syncGlossary = useCallback(async () => {
    const r = await fetch("/api/files");
    const data = await r.json();
    const glossary: Record<string, string> = {};
    for (const f of data.files || []) {
      if (String(f.path).startsWith("glossary/")) glossary[f.path] = f.content;
    }
    await fetch(`${serverUrl.replace(/\/$/, "")}/api/glossary`, {
      method: "POST",
      headers,
      body: JSON.stringify({ files: glossary }),
    });
  }, [headers, serverUrl]);

  const processJob = useCallback(
    async (job: NlpJob) => {
      setOllama("busy");
      const r = await fetch("/api/ollama", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...job, model: config.ollama_model }),
      });
      const result = await r.json();
      await fetch(`${serverUrl.replace(/\/$/, "")}/api/nlp/result`, {
        method: "POST",
        headers,
        body: JSON.stringify(result),
      });
      setJobs((j) => j.filter((x) => x.id !== job.id));
      await pingOllama();
    },
    [config.ollama_model, headers, pingOllama, serverUrl]
  );

  const requestFlush = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "flush_logs" }));
  }, []);

  const handleWsMessage = useCallback(
    async (raw: string) => {
      const msg = JSON.parse(raw);
      if (msg.type === "snapshot") {
        if (msg.config) setConfig(msg.config);
        setJobs(msg.nlp_queue || []);
        setLogs(msg.logs || []);
        for (const job of msg.nlp_queue || []) await processJob(job);
        requestFlush();
      }
      if (msg.type === "config" && msg.config) setConfig(msg.config);
      if (msg.type === "log" && msg.line) setLogs((l) => [...l.slice(-500), msg.line]);
      if (msg.type === "nlp_job" && msg.job) {
        setJobs((j) => [...j, msg.job]);
        await processJob(msg.job);
      }
      if (msg.type === "md" && msg.doc) {
        await fetch("/api/files", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            path: msg.doc.path,
            content: msg.doc.content,
            append: String(msg.doc.path).startsWith("todos/") || String(msg.doc.path).startsWith("logs/"),
          }),
        });
        await fetch(`${serverUrl.replace(/\/$/, "")}/api/md/ack`, {
          method: "POST",
          headers,
          body: JSON.stringify({ paths: [msg.doc.path] }),
        });
        await reloadFiles();
      }
      if (msg.type === "logs_dump" && msg.content) {
        await fetch("/api/files", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: msg.filename, content: msg.content, append: true }),
        });
        await reloadFiles();
      }
    },
    [headers, processJob, reloadFiles, requestFlush, serverUrl]
  );

  const connect = useCallback(() => {
    wsRef.current?.close();
    const http = serverUrl.replace(/\/$/, "");
    const ws = http.replace(/^http/, "ws") + `/ws?secret=${encodeURIComponent(secret)}`;
    const socket = new WebSocket(ws);
    wsRef.current = socket;
    socket.onopen = async () => {
      setConnected(true);
      await syncGlossary();
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (ev) => {
      void handleWsMessage(ev.data);
    };
  }, [handleWsMessage, secret, serverUrl, syncGlossary]);

  useEffect(() => {
    void reloadFiles();
    void pingOllama();
    const id = window.setInterval(() => void pingOllama(), 15000);
    return () => window.clearInterval(id);
  }, [pingOllama, reloadFiles]);

  useEffect(() => {
    if (!connected || !config.logging_enabled) return;
    const ms = Math.max(1, config.log_flush_interval_minutes) * 60 * 1000;
    flushTimer.current = window.setInterval(requestFlush, ms);
    return () => {
      if (flushTimer.current) window.clearInterval(flushTimer.current);
    };
  }, [connected, config.log_flush_interval_minutes, config.logging_enabled, requestFlush]);

  useEffect(() => {
    if (selectedFile) setEditor(selectedFile.content);
  }, [selectedFile]);

  async function saveConfig() {
    const r = await fetch(`${serverUrl.replace(/\/$/, "")}/api/config`, {
      method: "PUT",
      headers,
      body: JSON.stringify(config),
    });
    setSaveMsg(r.ok ? "Сохранено на сервере" : "Ошибка сохранения");
    wsRef.current?.send(JSON.stringify({ type: "config", config }));
    await syncGlossary();
  }

  async function saveFile() {
    if (!selected) return;
    await fetch("/api/files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: selected, content: editor, append: false }),
    });
    await reloadFiles();
    if (selected.startsWith("glossary/")) await syncGlossary();
    setSaveMsg("Файл записан");
  }

  const ollamaTone = ollama === "idle" ? "ok" : ollama === "busy" ? "busy" : "bad";

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Админ закрытого чата</h1>
          <p className="text-sm text-zinc-500">Локальный GUI: тексты, правила, .md и Ollama по запросу.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={connected ? "ok" : "bad"}>{connected ? "сервер онлайн" : "нет сокета"}</Badge>
          <Badge tone={ollamaTone}>Ollama: {ollama}</Badge>
        </div>
      </header>

      <Card className="grid gap-3 md:grid-cols-3">
        <div className="space-y-1 md:col-span-1">
          <Label>URL сервера</Label>
          <Input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Секрет синка</Label>
          <Input value={secret} onChange={(e) => setSecret(e.target.value)} type="password" />
        </div>
        <div className="flex items-end gap-2">
          <Button onClick={connect}>Подключить</Button>
          <Button variant="outline" onClick={requestFlush}>
            Забрать логи
          </Button>
        </div>
        {saveMsg ? <p className="text-sm text-zinc-500 md:col-span-3">{saveMsg}</p> : null}
      </Card>

      <Tabs defaultValue="texts">
        <TabsList>
          <TabsTrigger value="texts">Тексты</TabsTrigger>
          <TabsTrigger value="rules">Правила</TabsTrigger>
          <TabsTrigger value="lists">Списки</TabsTrigger>
          <TabsTrigger value="files">Файлы .md</TabsTrigger>
          <TabsTrigger value="logs">Логи и NLP</TabsTrigger>
        </TabsList>

        <TabsContent value="texts" className="mt-4 space-y-4">
          <Field label="Приветствие">
            <Textarea rows={5} value={config.welcome_text} onChange={(e) => setConfig({ ...config, welcome_text: e.target.value })} />
          </Field>
          <Field label="Предупреждение неактивным ({mention})">
            <Textarea rows={3} value={config.inactive_warning_text} onChange={(e) => setConfig({ ...config, inactive_warning_text: e.target.value })} />
          </Field>
          <Field label="Уведомление о муте ({minutes})">
            <Textarea rows={2} value={config.mute_notice} onChange={(e) => setConfig({ ...config, mute_notice: e.target.value })} />
          </Field>
          <Field label="Нет термина">
            <Input value={config.missing_term_reply} onChange={(e) => setConfig({ ...config, missing_term_reply: e.target.value })} />
          </Field>
        </TabsContent>

        <TabsContent value="rules" className="mt-4 grid gap-4 md:grid-cols-2">
          <Toggle
            label="Кик без анкеты"
            checked={config.questionnaire_kick_enabled}
            onChange={(v) => setConfig({ ...config, questionnaire_kick_enabled: v })}
          />
          <Num label="Минут на анкету" value={config.questionnaire_timeout_minutes} onChange={(v) => setConfig({ ...config, questionnaire_timeout_minutes: v })} />
          <Toggle label="Логирование" checked={config.logging_enabled} onChange={(v) => setConfig({ ...config, logging_enabled: v })} />
          <Num label="Интервал выгрузки логов, мин" value={config.log_flush_interval_minutes} onChange={(v) => setConfig({ ...config, log_flush_interval_minutes: v })} />
          <Toggle label="Пинг наименее активного" checked={config.inactive_warning_enabled} onChange={(v) => setConfig({ ...config, inactive_warning_enabled: v })} />
          <Num label="Часы между пингами" value={config.inactive_check_hours} onChange={(v) => setConfig({ ...config, inactive_check_hours: v })} />
          <Num label="Мут, секунд" value={config.mute_seconds} onChange={(v) => setConfig({ ...config, mute_seconds: v })} />
          <Num label="Длинный пост, символов" value={config.long_post_chars} onChange={(v) => setConfig({ ...config, long_post_chars: v })} />
          <Num label="Серия постов" value={config.long_post_burst} onChange={(v) => setConfig({ ...config, long_post_burst: v })} />
          <Toggle label="NLP для мата (Ollama)" checked={config.nlp_profanity} onChange={(v) => setConfig({ ...config, nlp_profanity: v })} />
          <Field label="Модель Ollama">
            <Input value={config.ollama_model} onChange={(e) => setConfig({ ...config, ollama_model: e.target.value })} list="models" />
            <datalist id="models">
              {models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </Field>
          <Field label="chat_id (подставится сам)">
            <Input
              value={config.chat_id ?? ""}
              onChange={(e) => setConfig({ ...config, chat_id: e.target.value ? Number(e.target.value) : null })}
            />
          </Field>
        </TabsContent>

        <TabsContent value="lists" className="mt-4 space-y-4">
          <Field label="ID каналов для авторепоста (через запятую)">
            <Input
              value={config.channel_ids.join(", ")}
              onChange={(e) =>
                setConfig({
                  ...config,
                  channel_ids: e.target.value
                    .split(",")
                    .map((s) => Number(s.trim()))
                    .filter((n) => Number.isFinite(n) && n !== 0),
                })
              }
            />
          </Field>
          <Field label="Запрещённые выражения (по одному на строку)">
            <Textarea
              rows={6}
              value={config.forbidden_words.join("\n")}
              onChange={(e) => setConfig({ ...config, forbidden_words: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
            />
          </Field>
          <Field label="Чёрный список user_id (по одному на строку)">
            <Textarea
              rows={4}
              value={config.blacklist.join("\n")}
              onChange={(e) =>
                setConfig({
                  ...config,
                  blacklist: e.target.value
                    .split("\n")
                    .map((s) => Number(s.trim()))
                    .filter((n) => Number.isFinite(n) && n !== 0),
                })
              }
            />
          </Field>
        </TabsContent>

        <TabsContent value="files" className="mt-4 grid gap-4 md:grid-cols-[240px_1fr]">
          <div className="max-h-[480px] space-y-1 overflow-auto rounded-lg border border-zinc-200 p-2 text-sm dark:border-zinc-800">
            {files.length === 0 ? <p className="p-2 text-zinc-500">Нет .md в data/</p> : null}
            {files.map((f) => (
              <button
                key={f.path}
                className={`block w-full rounded px-2 py-1 text-left ${selected === f.path ? "bg-zinc-100 dark:bg-zinc-800" : ""}`}
                onClick={() => setSelected(f.path)}
              >
                {f.path}
              </button>
            ))}
          </div>
          <div className="space-y-2">
            <Label>{selected || "выберите файл"}</Label>
            <Textarea rows={18} value={editor} onChange={(e) => setEditor(e.target.value)} className="font-mono" />
            <Button onClick={saveFile} disabled={!selected}>
              Сохранить файл
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="logs" className="mt-4 grid gap-4 md:grid-cols-2">
          <Card>
            <h2 className="mb-2 font-medium">Очередь NLP</h2>
            {jobs.length === 0 ? <p className="text-sm text-zinc-500">Пусто — Ollama не вызывается.</p> : null}
            <ul className="space-y-2 text-sm">
              {jobs.map((j) => (
                <li key={j.id} className="rounded border border-zinc-200 p-2 dark:border-zinc-800">
                  {j.kind} · {j.id.slice(0, 8)}
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <h2 className="mb-2 font-medium">Хвост лога на сервере</h2>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{logs.slice(-80).join("\n") || "Пока пусто"}</pre>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button onClick={saveConfig}>Сохранить настройки на сервер</Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <Label>{label}</Label>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function Num({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <Field label={label}>
      <Input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </Field>
  );
}
