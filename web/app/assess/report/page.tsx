"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { CitationChip } from "@/components/CitationChip";
import { SourceModal } from "@/components/SourceViewer";
import { Card, ErrorNote, Loading, PageTitle, ProgressBar } from "@/components/ui";
import { api, type Citation } from "@/lib/api";
import { masteryColor, pct } from "@/lib/util";
import { useApi } from "@/lib/useApi";

export default function ReportPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Report />
    </Suspense>
  );
}

function Report() {
  const id = useSearchParams().get("id") ?? "";
  const { data, error, loading } = useApi(() => api.report(id), id);
  const [open, setOpen] = useState<Citation | null>(null);

  if (!id) return <ErrorNote message="Missing assessment id." />;
  if (loading) return <Loading label="Building your report" />;
  if (error || !data) return <ErrorNote message={error} />;

  const score = data.total ? data.correct / data.total : 0;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageTitle sub={`${data.answered} of ${data.total} answered`}>Report</PageTitle>

      <Card>
        <p className="text-sm text-muted">Overall score</p>
        <p className="text-4xl font-semibold">{pct(score)}</p>
        <p className="text-sm text-muted">
          {data.correct} correct out of {data.total}
        </p>
      </Card>

      <section aria-labelledby="topics-h" className="space-y-2">
        <h2 id="topics-h" className="text-lg font-semibold">
          By topic
        </h2>
        {data.score_by_topic.map((t) => (
          <Card key={t.topic_id} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span>{t.name}</span>
              <span className="text-muted">
                {t.correct}/{t.total} · {pct(t.score)}
              </span>
            </div>
            <ProgressBar value={t.score} color={masteryColor(t.score)} label={`${t.name} score`} />
          </Card>
        ))}
      </section>

      {data.mastery_changes.length > 0 && (
        <section aria-labelledby="mc-h" className="space-y-2">
          <h2 id="mc-h" className="text-lg font-semibold">
            Mastery changes
          </h2>
          <Card>
            <ul className="divide-y divide-line text-sm">
              {data.mastery_changes.map((m) => (
                <li key={m.concept_id} className="flex flex-wrap justify-between gap-2 py-2">
                  <span>{m.name}</span>
                  <span className={m.delta >= 0 ? "text-good" : "text-bad"}>
                    {pct(m.before)} → {pct(m.after)}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {data.weak_topics.length > 0 && (
        <section aria-labelledby="weak-h" className="space-y-2">
          <h2 id="weak-h" className="text-lg font-semibold">
            Weak topics
          </h2>
          <ul className="flex flex-wrap gap-2">
            {data.weak_topics.map((t) => (
              <li key={t.topic_id} className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-1 text-sm">
                {t.name} · {pct(t.mastery)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.misconceptions.length > 0 && (
        <section aria-labelledby="mis-h" className="space-y-2">
          <h2 id="mis-h" className="text-lg font-semibold">
            Misconceptions to fix
          </h2>
          <Card>
            <ul className="space-y-1 text-sm">
              {data.misconceptions.map((m) => (
                <li key={m.label} className="flex justify-between gap-2">
                  <span>{m.label}</span>
                  <span className="text-muted">×{m.count}</span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {data.next_units.length > 0 && (
        <section aria-labelledby="next-h" className="space-y-2">
          <h2 id="next-h" className="text-lg font-semibold">
            Next units to study
          </h2>
          <Card>
            <ul className="space-y-2 text-sm">
              {data.next_units.map((u) => (
                <li key={u.unit_id} className="flex flex-wrap items-center gap-2">
                  <CitationChip citation={u} onOpen={setOpen} />
                  <span className="text-muted">{u.source_title}</span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      <Link href="/assess" className="inline-block text-sm underline">
        Take another assessment
      </Link>
      <SourceModal citation={open} onClose={() => setOpen(null)} />
    </div>
  );
}
