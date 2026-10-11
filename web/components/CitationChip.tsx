import type { Citation } from "@/lib/api";

export function CitationChip({ citation, onOpen }: { citation: Citation; onOpen: (c: Citation) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      title={`${citation.source_title} · ${citation.label}`}
      aria-label={`Open source: ${citation.source_title}, ${citation.label}`}
      className="mx-0.5 inline-flex min-h-6 items-center rounded-md border border-accent/40 bg-accent/10 px-1.5 text-xs font-medium text-accent hover:bg-accent/20"
    >
      {citation.label}
    </button>
  );
}

export function CitationList({ citations, onOpen }: { citations: Citation[]; onOpen: (c: Citation) => void }) {
  if (citations.length === 0) return null;
  return (
    <p className="flex flex-wrap items-center gap-1 text-sm">
      <span className="text-muted">Sources:</span>
      {citations.map((c) => (
        <CitationChip key={c.unit_id} citation={c} onOpen={onOpen} />
      ))}
    </p>
  );
}
