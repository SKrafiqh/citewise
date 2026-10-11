"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorNote, Loading, PageTitle } from "@/components/ui";
import { api, errorMessage, type AssessKind, type Concept, type Mix, type QType, type Topic } from "@/lib/api";
import { compactScope } from "@/lib/util";
import { sessionSet, useStudent } from "@/lib/student";
import { useApi } from "@/lib/useApi";

const COUNTS = [5, 10, 15];
const PRESETS: { label: string; mix: Record<QType, number> }[] = [
  { label: "Balanced", mix: { mcq: 6, short: 2, numerical: 2 } },
  { label: "MCQ only", mix: { mcq: 1, short: 0, numerical: 0 } },
];
const QTYPE_LABEL: Record<QType, string> = { mcq: "Multiple choice", short: "Short answer", numerical: "Numerical" };

export default function AssessPage() {
  const studentId = useStudent();
  const router = useRouter();
  const concepts = useApi(api.concepts, "concepts");
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());
  const [n, setN] = useState(10);
  const [kind, setKind] = useState<Extract<AssessKind, "quiz" | "mock_exam">>("quiz");
  const [mix, setMix] = useState<Record<QType, number>>(PRESETS[0].mix);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shortfall, setShortfall] = useState<{ id: string; got: number } | null>(null);

  const toggle = (ids: string[], on: boolean) =>
    setChecked((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });

  const mixTotal = mix.mcq + mix.short + mix.numerical;

  async function start() {
    setBusy(true);
    setError(null);
    setShortfall(null);
    try {
      const body: Mix = {};
      (Object.keys(mix) as QType[]).forEach((k) => mix[k] > 0 && (body[k] = mix[k]));
      const a = await api.createAssessment({
        student_id: studentId,
        kind,
        scope: compactScope(concepts.data?.topics ?? [], checked),
        n,
        mix: body,
      });
      sessionSet(`assessment:${a.assessment_id}`, a.questions);
      if (a.shortfall > 0) {
        setShortfall({ id: a.assessment_id, got: a.questions.length });
      } else {
        router.push(`/assess/run?id=${encodeURIComponent(a.assessment_id)}`);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageTitle sub="Pick what to practise. Leave everything unchecked to cover the whole course.">New assessment</PageTitle>

      <section aria-labelledby="scope-h" className="space-y-2">
        <h2 id="scope-h" className="text-lg font-semibold">
          Scope
        </h2>
        {concepts.loading && <Loading label="Loading topics" />}
        <ErrorNote message={concepts.error} />
        {concepts.data?.topics.map((t) => (
          <TopicNode key={t.id} topic={t} checked={checked} toggle={toggle} />
        ))}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card className="space-y-2">
          <fieldset>
            <legend className="mb-2 font-medium">Type</legend>
            <div className="flex gap-2">
              {(["quiz", "mock_exam"] as const).map((k) => (
                <Choice key={k} name="kind" checked={kind === k} onChange={() => setKind(k)}>
                  {k === "quiz" ? "Quiz" : "Mock exam"}
                </Choice>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="mb-2 mt-3 font-medium">Questions</legend>
            <div className="flex gap-2">
              {COUNTS.map((c) => (
                <Choice key={c} name="n" checked={n === c} onChange={() => setN(c)}>
                  {c}
                </Choice>
              ))}
            </div>
          </fieldset>
        </Card>

        <Card>
          <fieldset className="space-y-3">
            <legend className="mb-1 font-medium">Question mix</legend>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <Button key={p.label} variant="ghost" onClick={() => setMix(p.mix)}>
                  {p.label}
                </Button>
              ))}
            </div>
            {(Object.keys(QTYPE_LABEL) as QType[]).map((k) => (
              <div key={k}>
                <label htmlFor={`mix-${k}`} className="flex justify-between text-sm">
                  <span>{QTYPE_LABEL[k]}</span>
                  <span className="text-muted">
                    {mixTotal ? Math.round((mix[k] / mixTotal) * 100) : 0}%
                  </span>
                </label>
                <input
                  id={`mix-${k}`}
                  type="range"
                  min={0}
                  max={10}
                  value={mix[k]}
                  onChange={(e) => setMix((m) => ({ ...m, [k]: Number(e.target.value) }))}
                  className="w-full accent-[var(--accent)]"
                />
              </div>
            ))}
          </fieldset>
        </Card>
      </section>

      <ErrorNote message={error} />
      {shortfall && (
        <div role="status" className="space-y-2 rounded-xl border border-warn/50 bg-warn/10 p-3 text-sm">
          <p>Only {shortfall.got} questions were available for this scope.</p>
          <Button onClick={() => router.push(`/assess/run?id=${encodeURIComponent(shortfall.id)}`)}>Start anyway</Button>
        </div>
      )}
      <Button onClick={start} disabled={busy || mixTotal === 0 || concepts.loading}>
        {busy ? "Generating questions…" : "Start"}
      </Button>
    </div>
  );
}

function Choice({
  name,
  checked,
  onChange,
  children,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex min-h-10 cursor-pointer items-center justify-center rounded-lg border border-line px-4 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent/10 has-[:checked]:font-medium has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent">
      <input type="radio" name={name} checked={checked} onChange={onChange} className="sr-only" />
      {children}
    </label>
  );
}

function Check({ ids, checked, toggle, children }: { ids: string[]; checked: ReadonlySet<string>; toggle: (ids: string[], on: boolean) => void; children: React.ReactNode }) {
  const count = ids.filter((id) => checked.has(id)).length;
  return (
    <label className="flex min-h-8 items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={ids.length > 0 && count === ids.length}
        ref={(el) => {
          if (el) el.indeterminate = count > 0 && count < ids.length;
        }}
        onChange={(e) => toggle(ids, e.target.checked)}
      />
      {children}
    </label>
  );
}

function TopicNode({ topic, checked, toggle }: { topic: Topic; checked: ReadonlySet<string>; toggle: (ids: string[], on: boolean) => void }) {
  const ids = (cs: Concept[]) => cs.map((c) => c.id);
  return (
    <details className="rounded-xl border border-line bg-surface p-3">
      <summary className="cursor-pointer font-medium">{topic.name}</summary>
      <div className="mt-2 space-y-2 pl-1">
        <Check ids={ids(topic.subtopics.flatMap((s) => s.concepts))} checked={checked} toggle={toggle}>
          <span className="text-muted">Whole topic</span>
        </Check>
        {topic.subtopics.map((s) => (
          <div key={s.id} className="ml-4 space-y-1">
            <Check ids={ids(s.concepts)} checked={checked} toggle={toggle}>
              <span className="font-medium">{s.name}</span>
            </Check>
            <div className="ml-6 space-y-0.5">
              {s.concepts.map((c) => (
                <Check key={c.id} ids={[c.id]} checked={checked} toggle={toggle}>
                  {c.name}
                </Check>
              ))}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
