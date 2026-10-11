"use client";

import { useEffect, useRef, useState } from "react";
import { ChatAnswer } from "@/components/ChatAnswer";
import { SourceViewer } from "@/components/SourceViewer";
import { Button, Card, ErrorNote, FIELD } from "@/components/ui";
import { api, errorMessage, type ChatResponse, type Citation } from "@/lib/api";
import { useStudent } from "@/lib/student";

type Lang = "en" | "hi";
type Turn = { id: number; question: string; lang: Lang; response?: ChatResponse; error?: string };

export default function TutorPage() {
  const studentId = useStudent();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [allowOutside, setAllowOutside] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<Citation | null>(null);
  const viewerRef = useRef<HTMLElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) viewerRef.current?.scrollIntoView({ block: "nearest" });
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    const id = turns.length;
    setTurns((t) => [...t, { id, question, lang }]);
    setInput("");
    setBusy(true);
    const patch = (p: Partial<Turn>) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, ...p } : x)));
    try {
      patch({ response: await api.chat({ student_id: studentId, question, allow_outside: allowOutside, lang }) });
    } catch (e) {
      patch({ error: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <aside
        ref={viewerRef}
        aria-label="Source panel"
        className={`${open ? "block" : "hidden"} order-first self-start rounded-xl border border-line bg-surface p-4 lg:sticky lg:top-4 lg:order-last lg:block`}
      >
        <SourceViewer citation={open} />
        {open && (
          <Button variant="ghost" className="mt-3 lg:hidden" onClick={() => setOpen(null)}>
            Close source
          </Button>
        )}
      </aside>

      <section aria-label="Conversation" className="flex min-w-0 flex-col gap-4">
        <div role="log" aria-live="polite" className="space-y-4">
          {turns.length === 0 && (
            <Card>
              <p className="font-medium">Ask anything about your course.</p>
              <p className="text-sm text-muted">Every answer links back to the exact page, slide or video moment.</p>
            </Card>
          )}
          {turns.map((t) => (
            <div key={t.id} className="space-y-2">
              <p lang={t.lang} className="ml-auto w-fit max-w-[85%] rounded-xl bg-accent px-3 py-2 text-sm text-accent-fg">
                {t.question}
              </p>
              <Card>
                {t.response ? (
                  <ChatAnswer response={t.response} lang={t.lang} onCite={setOpen} />
                ) : t.error ? (
                  <ErrorNote message={t.error} />
                ) : (
                  <p role="status" className="text-sm text-muted">
                    Searching your sources…
                  </p>
                )}
              </Card>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="space-y-2"
        >
          <label htmlFor="q" className="sr-only">
            Your question
          </label>
          <textarea
            id="q"
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={lang === "hi" ? "अपना प्रश्न लिखें…" : "Ask a question about your course…"}
            className={FIELD}
          />
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={allowOutside} onChange={(e) => setAllowOutside(e.target.checked)} />
              Allow outside knowledge
            </label>
            <div role="group" aria-label="Answer language" className="flex gap-1">
              {(["en", "hi"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  aria-pressed={lang === l}
                  onClick={() => setLang(l)}
                  className={`min-h-9 rounded-lg border px-3 text-sm ${lang === l ? "border-accent bg-accent/10 font-medium" : "border-line"}`}
                >
                  {l === "en" ? "English" : "हिन्दी"}
                </button>
              ))}
            </div>
            <Button type="submit" disabled={busy || !input.trim()} className="ml-auto">
              {busy ? "Thinking…" : "Ask"}
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}
