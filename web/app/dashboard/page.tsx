"use client";

import { useState } from "react";
import { CitationList } from "@/components/CitationChip";
import { SourceModal } from "@/components/SourceViewer";
import { Badge, Card, ErrorNote, Loading, PageTitle, ProgressBar } from "@/components/ui";
import { api, type Citation, type MasteryConcept } from "@/lib/api";
import { masteryColor, pct } from "@/lib/util";
import { useStudent } from "@/lib/student";
import { useApi } from "@/lib/useApi";

export default function DashboardPage() {
  const studentId = useStudent();
  const mastery = useApi(() => api.mastery(studentId), `mastery:${studentId}`);
  const recs = useApi(() => api.recommendations(studentId), `recs:${studentId}`);
  const [open, setOpen] = useState<Citation | null>(null);

  const byTopic = new Map<string, MasteryConcept[]>();
  mastery.data?.concepts.forEach((c) => byTopic.set(c.topic_id, [...(byTopic.get(c.topic_id) ?? []), c]));

  return (
    <div className="space-y-8">
      <PageTitle sub="How well you know each concept, and what to study next.">Dashboard</PageTitle>

      <section aria-labelledby="rec-h" className="space-y-3">
        <h2 id="rec-h" className="text-lg font-semibold">
          Recommended next
        </h2>
        {recs.loading && <Loading />}
        <ErrorNote message={recs.error} />
        {recs.data?.length === 0 && <p className="text-sm text-muted">Nothing to recommend yet. Take a quiz first.</p>}
        <ul className="grid gap-3 sm:grid-cols-2">
          {recs.data?.map((r) => (
            <li key={r.concept_id}>
              <Card className="h-full space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="font-medium">{r.name}</h3>
                  <span className="text-sm text-muted">{pct(r.p_known)}</span>
                </div>
                <p className="text-sm text-muted">{r.reason}</p>
                <CitationList citations={r.units} onOpen={setOpen} />
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="mastery-h" className="space-y-3">
        <h2 id="mastery-h" className="text-lg font-semibold">
          Mastery by topic
        </h2>
        {mastery.loading && <Loading />}
        <ErrorNote message={mastery.error} />
        {mastery.data?.topics.map((t) => (
          <Card key={t.topic_id} className="space-y-3">
            <div className="space-y-1">
              <div className="flex justify-between">
                <h3 className="font-medium">{t.name}</h3>
                <span className="text-sm text-muted">avg {pct(t.mean)}</span>
              </div>
              <ProgressBar value={t.mean} color={masteryColor(t.mean)} label={`${t.name} average mastery`} />
            </div>
            <ul className="space-y-2">
              {(byTopic.get(t.topic_id) ?? []).map((c) => (
                <li key={c.concept_id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-sm">
                  <span className="flex flex-wrap items-center gap-2">
                    {c.name}
                    {c.due && <Badge tone="warn">Review due</Badge>}
                  </span>
                  <span className="text-muted">{pct(c.p_known)}</span>
                  <div className="col-span-2">
                    <ProgressBar value={c.p_known} color={masteryColor(c.p_known)} label={`${c.name} mastery`} />
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </section>
      <SourceModal citation={open} onClose={() => setOpen(null)} />
    </div>
  );
}
