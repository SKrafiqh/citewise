import type { Citation, Concept, Edge, Topic } from "./api";

export const pct = (p: number) => `${Math.round(p * 100)}%`;

export type MasteryLevel = "low" | "mid" | "high";
export const masteryLevel = (p: number): MasteryLevel => (p < 0.4 ? "low" : p < 0.7 ? "mid" : "high");
export const MASTERY_COLOR: Record<MasteryLevel, string> = {
  low: "var(--bad)",
  mid: "var(--warn)",
  high: "var(--good)",
};
export const masteryColor = (p: number) => MASTERY_COLOR[masteryLevel(p)];

export const citationsById = (citations: Citation[]): Map<string, Citation> =>
  new Map(citations.map((c) => [c.unit_id, c]));

export const flattenConcepts = (topics: Topic[]): Concept[] =>
  topics.flatMap((t) => t.subtopics.flatMap((s) => s.concepts));

/** Coarsest ids covering the checked concepts: whole topic > whole subtopic > single concepts. */
export function compactScope(topics: Topic[], checked: ReadonlySet<string>): string[] {
  const ids: string[] = [];
  for (const t of topics) {
    const all = t.subtopics.flatMap((s) => s.concepts);
    if (all.length > 0 && all.every((c) => checked.has(c.id))) {
      ids.push(t.id);
      continue;
    }
    for (const s of t.subtopics) {
      if (s.concepts.length > 0 && s.concepts.every((c) => checked.has(c.id))) ids.push(s.id);
      else ids.push(...s.concepts.filter((c) => checked.has(c.id)).map((c) => c.id));
    }
  }
  return ids;
}

export const ts = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

/** Layered layout: x by depth (longest prerequisite chain), y by index in layer. Cycles are cut. */
export function layeredLayout(
  conceptIds: string[],
  edges: Edge[],
  dx = 260,
  dy = 90,
): Map<string, { x: number; y: number }> {
  const known = new Set(conceptIds);
  const prereqs = new Map<string, string[]>();
  for (const e of edges) {
    if (known.has(e.concept_id) && known.has(e.prereq_id)) {
      prereqs.set(e.concept_id, [...(prereqs.get(e.concept_id) ?? []), e.prereq_id]);
    }
  }
  const depth = new Map<string, number>();
  const visiting = new Set<string>();
  const depthOf = (id: string): number => {
    const cached = depth.get(id);
    if (cached !== undefined) return cached;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const d = Math.max(-1, ...(prereqs.get(id) ?? []).map(depthOf)) + 1;
    visiting.delete(id);
    depth.set(id, d);
    return d;
  };
  const rows = new Map<number, number>();
  const out = new Map<string, { x: number; y: number }>();
  for (const id of conceptIds) {
    const d = depthOf(id);
    const row = rows.get(d) ?? 0;
    rows.set(d, row + 1);
    out.set(id, { x: d * dx, y: row * dy });
  }
  return out;
}
