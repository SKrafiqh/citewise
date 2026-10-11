"use client";

import { useEffect, useRef } from "react";
import { API_URL, type Citation } from "@/lib/api";
import { Button } from "./ui";

export function SourceViewer({ citation }: { citation: Citation | null }) {
  if (!citation) {
    return <p className="text-sm text-muted">Select a citation to see the exact page, slide or video moment here.</p>;
  }
  const { modality, youtube_id, asset_url, locator } = citation;
  return (
    <article aria-label="Source viewer" className="space-y-3">
      <header>
        <h2 className="text-sm font-semibold">{citation.source_title}</h2>
        <p className="text-xs text-muted">
          {modality} · {citation.label}
        </p>
      </header>
      {modality === "video" && youtube_id ? (
        <div className="aspect-video w-full overflow-hidden rounded-lg bg-black">
          <iframe
            key={citation.unit_id}
            title={`${citation.source_title} at ${citation.label}`}
            src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(youtube_id)}?start=${Math.floor(locator.t_start ?? 0)}&autoplay=1`}
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
            className="h-full w-full"
          />
        </div>
      ) : modality === "video" ? (
        <p className="rounded-lg bg-soft px-3 py-2 text-sm text-muted">Video not available online. Transcript excerpt below.</p>
      ) : asset_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={API_URL + asset_url}
          alt={`${citation.source_title}, ${citation.label}`}
          className="w-full rounded-lg border border-line bg-white"
        />
      ) : null}
      <blockquote className="border-l-2 border-accent pl-3 text-sm text-muted">{citation.excerpt}</blockquote>
    </article>
  );
}

/** Modal wrapper (native <dialog>: focus trap, Esc and backdrop come for free). */
export function SourceModal({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (citation && !dialog.open) dialog.showModal();
    if (!citation && dialog.open) dialog.close();
  }, [citation]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-label="Source"
      className="m-auto max-h-[90vh] w-[min(40rem,calc(100%-2rem))] overflow-auto rounded-xl border border-line bg-surface p-4 text-fg backdrop:bg-black/50"
    >
      {citation && (
        <div className="space-y-3">
          <SourceViewer citation={citation} />
          <Button variant="ghost" onClick={onClose} autoFocus>
            Close
          </Button>
        </div>
      )}
    </dialog>
  );
}
