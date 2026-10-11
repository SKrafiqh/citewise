"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo, useState } from "react";
import { Card, ErrorNote, Loading, PageTitle } from "@/components/ui";
import { api, type Concept } from "@/lib/api";
import { flattenConcepts, layeredLayout, masteryColor, pct } from "@/lib/util";
import { useStudent } from "@/lib/student";
import { useApi } from "@/lib/useApi";

const NO_DATA_COLOR = "var(--muted)";

export default function MapPage() {
  const studentId = useStudent();
  const concepts = useApi(api.concepts, "concepts");
  const mastery = useApi(() => api.mastery(studentId), `mastery:${studentId}`);
  const [selected, setSelected] = useState<string | null>(null);

  const { nodes, edges, byId } = useMemo(() => {
    const list = flattenConcepts(concepts.data?.topics ?? []);
    const pos = layeredLayout(
      list.map((c) => c.id),
      concepts.data?.edges ?? [],
    );
    const p = new Map(mastery.data?.concepts.map((c) => [c.concept_id, c.p_known]));
    const nodes: Node[] = list.map((c) => {
      const known = p.get(c.id);
      return {
        id: c.id,
        position: pos.get(c.id) ?? { x: 0, y: 0 },
        data: { label: c.name },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        ariaLabel: `${c.name}, mastery ${known === undefined ? "unknown" : pct(known)}`,
        style: {
          width: 190,
          padding: 8,
          fontSize: 13,
          color: "var(--fg)",
          background: "var(--surface)",
          border: `3px solid ${known === undefined ? NO_DATA_COLOR : masteryColor(known)}`,
          borderRadius: 10,
        },
      };
    });
    const edges: Edge[] = (concepts.data?.edges ?? []).map((e) => ({
      id: `${e.prereq_id}->${e.concept_id}`,
      source: e.prereq_id,
      target: e.concept_id,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: "var(--muted)" },
    }));
    return { nodes, edges, byId: new Map<string, Concept>(list.map((c) => [c.id, c])) };
  }, [concepts.data, mastery.data]);

  const sel = selected ? byId.get(selected) : undefined;
  const selMastery = mastery.data?.concepts.find((c) => c.concept_id === selected);
  const nameOf = (id: string) => byId.get(id)?.name ?? id;

  return (
    <div className="space-y-4">
      <PageTitle sub="Arrows point from a prerequisite to the concept that builds on it. Border colour shows your mastery.">
        Course map
      </PageTitle>
      {(concepts.loading || mastery.loading) && <Loading />}
      <ErrorNote message={concepts.error ?? mastery.error} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="h-[60vh] min-h-80 overflow-hidden rounded-xl border border-line bg-surface">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodeClick={(_, n) => setSelected(n.id)}
            nodesDraggable={false}
            nodesConnectable={false}
            fitView
            minZoom={0.2}
            colorMode="system"
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <aside aria-label="Concept details">
          <Card className="space-y-2 text-sm">
            {sel ? (
              <>
                <h2 className="text-base font-semibold">{sel.name}</h2>
                <p>{sel.summary}</p>
                <p className="text-muted">
                  Mastery: {selMastery ? `${pct(selMastery.p_known)} from ${selMastery.n_obs} observations` : "not measured yet"}
                </p>
                {sel.prereqs.length > 0 && <p className="text-muted">Builds on: {sel.prereqs.map(nameOf).join(", ")}</p>}
              </>
            ) : (
              <p className="text-muted">Select a concept to see its summary and your mastery.</p>
            )}
          </Card>
          <p className="mt-3 flex flex-wrap gap-x-3 text-xs text-muted">
            <span style={{ color: "var(--bad)" }}>■ below 40%</span>
            <span style={{ color: "var(--warn)" }}>■ 40–70%</span>
            <span style={{ color: "var(--good)" }}>■ 70%+</span>
          </p>
        </aside>
      </div>
    </div>
  );
}
