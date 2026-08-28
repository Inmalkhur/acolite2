"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge, Card, Input, Label, Textarea } from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChatConfig, defaultChat, defaultRoot, isRootConfig, NlpJob, RootConfig } from "@/lib/types";

type FileRow = { path: string; content: string };
type OllamaStatus = "offline" | "idle" | "busy";

export function Dashboard() {
  const [serverUrl, setServerUrl] = useState("http://127.0.0.1:43121");
  const [secret, setSecret] = useState("change-me");
  const [connected, setConnected] = useState(false);
  const [root, setRoot] = useState<RootConfig>(defaultRoot);
  const [selectedId, setSelectedId] = useState("");
  const [manualId, setManualId] = useState("");
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
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const headers = useMemo(
    () => ({ "Content-Type": "application/json", "X-Sync-Secret": secret }),
    [secret]
  );

  const chatIds = Object.keys(root.chats).sort();
  const config = selectedId ? root.chats[selectedId] : undefined;
  const selectedFile = files.find((f) => f.path === selected);

  function applyIncomingConfig(incoming: RootConfig) {
    setRoot(incoming);
    const ids = Object.keys(incoming.chats);
    const keep = selectedIdRef.current;
    if (keep && incoming.chats[keep]) setSelectedId(keep);
    else if (ids.length) setSelectedId(ids[0]);
    else setSelectedId("");
  }

  function patchChat(partial: Partial<ChatConfig>) {
    if (!selectedId || !root.chats[selectedId]) return;
    setRoot({
      ...root,
      chats: { ...root.chats, [selectedId]: { ...root.chats[selectedId], ...partial } },
    });
  }

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
        body: JSON.stringify({ ...job, model: root.ollama_model }),
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
    [headers, pingOllama, root.ollama_model, serverUrl]
  );

  const requestFlush = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "flush_logs" }));
  }, []);

  const handleWsMessage = useCallback(
    async (raw: string) => {
      const msg = JSON.parse(raw);
      if (msg.type === "snapshot") {
        if (msg.config && isRootConfig(msg.config)) applyIncomingConfig(msg.config);
        setJobs(msg.nlp_queue || []);
        setLogs(msg.logs || []);
        for (const job of msg.nlp_queue || []) await processJob(job);
        requestFlush();
      }
      if (msg.type === "config" && msg.config && isRootConfig(msg.config)) {
        applyIncomingConfig(msg.config);
      }
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
    if (!connected) return;
    const ms = Math.max(1, root.log_flush_interval_minutes) * 60 * 1000;
    flushTimer.current = window.setInterval(requestFlush, ms);
    return () => {
      if (flushTimer.current) window.clearInterval(flushTimer.current);
    };
  }, [connected, requestFlush, root.log_flush_interval_minutes]);

  useEffect(() => {
    if (selectedFile) setEditor(selectedFile.content);
  }, [selectedFile]);

  async function saveConfig() {
    const r = await fetch(`${serverUrl.replace(/\/$/, "")}/api/config`, {
      method: "PUT",
      headers,
      body: JSON.stringify(root),
    });
    setSaveMsg(r.ok ? "Сохранено на сервере" : "Ошибка сохранения");
    wsRef.current?.send(JSON.stringify({ type: "config", config: root }));
    await syncGlossary();
  }

  function addManualChat() {
    const id = Number(manualId.trim());
    if (!Number.isFinite(id) || id === 0) {
      setSaveMsg("Укажите числовой chat_id");
      return;
    }
    const key = String(id);
    if (root.chats[key]) {
      setSelectedId(key);
      return;
    }
    setRoot({ ...root, chats: { ...root.chats, [key]: defaultChat(id) } });
    setSelectedId(key);
    setManualId("");
  }

  function removeSelected() {
    if (!selectedId) return;
    const next = { ...root.chats };
    delete next[selectedId];
    setRoot({ ...root, chats: next });
    const ids = Object.keys(next);
    setSelectedId(ids[0] || "");
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
          <p className="text-sm text-zinc-500">Каждый чат, куда добавлен бот, настраивается отдельно. ID подхватывается при добавлении.</p>
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
        <Field label="Модель Ollama (общая)">
          <Input value={root.ollama_model} onChange={(e) => setRoot({ ...root, ollama_model: e.target.value })} list="models" />
          <datalist id="models">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </Field>
        <Num
          label="Интервал выгрузки логов, мин"
          value={root.log_flush_interval_minutes}
          onChange={(v) => setRoot({ ...root, log_flush_interval_minutes: v })}
        />
        {saveMsg ? <p className="text-sm text-zinc-500 md:col-span-3">{saveMsg}</p> : null}
      </Card>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium">Чаты</h2>
          <p className="text-xs text-zinc-500">При добавлении бота в группу чат появится здесь сам.</p>
        </div>
        {chatIds.length === 0 ? (
          <p className="text-sm text-zinc-500">Пока нет чатов. Добавьте бота в группу или введите chat_id вручную.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {chatIds.map((id) => {
              const c = root.chats[id];
              const active = id === selectedId;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSelectedId(id)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm ${
                    active ? "border-zinc-900 bg-zinc-100 dark:border-zinc-100 dark:bg-zinc-800" : "border-zinc-200 dark:border-zinc-800"
                  }`}
                >
                  <div className="font-medium">{c.title || id}</div>
                  <div className="text-xs text-zinc-500">
                    {id}
                    {c.enabled ? "" : " · выкл"}
                  </div>
                </button>
              );
            })}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="chat_id вручную, например -100123"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            className="max-w-xs"
          />
          <Button variant="outline" onClick={addManualChat}>
            Добавить чат
          </Button>
          <Button variant="outline" onClick={removeSelected} disabled={!selectedId}>
            Убрать из списка
          </Button>
        </div>
      </Card>

      {!config ? (
        <p className="text-sm text-zinc-500">Выберите чат, чтобы править его тексты и правила.</p>
      ) : (
        <>
          <Tabs defaultValue="texts">
            <TabsList>
              <TabsTrigger value="texts">Тексты</TabsTrigger>
              <TabsTrigger value="rules">Правила</TabsTrigger>
              <TabsTrigger value="lists">Списки</TabsTrigger>
              <TabsTrigger value="files">Файлы .md</TabsTrigger>
              <TabsTrigger value="logs">Логи и NLP</TabsTrigger>
            </TabsList>

            <TabsContent value="texts" className="mt-4 space-y-4">
              <Field label="Название в GUI">
                <Input value={config.title} onChange={(e) => patchChat({ title: e.target.value })} />
              </Field>
              <Field label="Приветствие">
                <Textarea rows={5} value={config.welcome_text} onChange={(e) => patchChat({ welcome_text: e.target.value })} />
              </Field>
              <Field label="Предупреждение неактивным ({mention})">
                <Textarea rows={3} value={config.inactive_warning_text} onChange={(e) => patchChat({ inactive_warning_text: e.target.value })} />
              </Field>
              <Field label="Уведомление о муте ({minutes})">
                <Textarea rows={2} value={config.mute_notice} onChange={(e) => patchChat({ mute_notice: e.target.value })} />
              </Field>
              <Field label="Нет термина">
                <Input value={config.missing_term_reply} onChange={(e) => patchChat({ missing_term_reply: e.target.value })} />
              </Field>
            </TabsContent>

            <TabsContent value="rules" className="mt-4 grid gap-4 md:grid-cols-2">
              <Toggle label="Бот активен в этом чате" checked={config.enabled} onChange={(v) => patchChat({ enabled: v })} />
              <Field label="chat_id (авто)">
                <Input value={config.chat_id} readOnly />
              </Field>
              <Toggle label="Кик без анкеты" checked={config.questionnaire_kick_enabled} onChange={(v) => patchChat({ questionnaire_kick_enabled: v })} />
              <Num label="Минут на анкету" value={config.questionnaire_timeout_minutes} onChange={(v) => patchChat({ questionnaire_timeout_minutes: v })} />
              <Toggle label="Логирование" checked={config.logging_enabled} onChange={(v) => patchChat({ logging_enabled: v })} />
              <Toggle label="Пинг наименее активного" checked={config.inactive_warning_enabled} onChange={(v) => patchChat({ inactive_warning_enabled: v })} />
              <Num label="Часы между пингами" value={config.inactive_check_hours} onChange={(v) => patchChat({ inactive_check_hours: v })} />
              <Num label="Мут, секунд" value={config.mute_seconds} onChange={(v) => patchChat({ mute_seconds: v })} />
              <Num label="Длинный пост, символов" value={config.long_post_chars} onChange={(v) => patchChat({ long_post_chars: v })} />
              <Num label="Серия постов" value={config.long_post_burst} onChange={(v) => patchChat({ long_post_burst: v })} />
              <Toggle label="NLP для мата (Ollama)" checked={config.nlp_profanity} onChange={(v) => patchChat({ nlp_profanity: v })} />
            </TabsContent>

            <TabsContent value="lists" className="mt-4 space-y-4">
              <Field label="ID каналов для авторепоста в этот чат (через запятую)">
                <Input
                  value={config.channel_ids.join(", ")}
                  onChange={(e) =>
                    patchChat({
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
                  onChange={(e) => patchChat({ forbidden_words: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
                />
              </Field>
              <Field label="Чёрный список user_id (по одному на строку)">
                <Textarea
                  rows={4}
                  value={config.blacklist.join("\n")}
                  onChange={(e) =>
                    patchChat({
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
        </>
      )}

      {!config ? (
        <div className="flex justify-end">
          <Button onClick={saveConfig}>Сохранить настройки на сервер</Button>
        </div>
      ) : null}
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
