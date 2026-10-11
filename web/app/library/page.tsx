"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorNote, FIELD, Loading, PageTitle } from "@/components/ui";
import { ApiError, api, errorMessage, type Source, type SourceStatus } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const POLL_MS = 3000;
const TONE: Record<SourceStatus, "neutral" | "good" | "warn" | "bad"> = {
  pending: "neutral",
  ingesting: "warn",
  ready: "good",
  failed: "bad",
};

function adminError(e: unknown): string {
  if (e instanceof ApiError && e.status === 401) return `Admin token rejected. ${e.detail}`;
  if (e instanceof ApiError && e.status === 503) return `Uploads are not available on the server. ${e.detail}`;
  return errorMessage(e);
}

export default function LibraryPage() {
  const sources = useApi(api.sources, "sources");
  const { data, reload } = sources;
  const [token, setToken] = useState("");

  const busy = data?.some((s) => s.status === "pending" || s.status === "ingesting") ?? false;
  useEffect(() => {
    if (!busy) return;
    const timer = setTimeout(reload, POLL_MS);
    return () => clearTimeout(timer);
  }, [busy, data, reload]);

  return (
    <div className="space-y-8">
      <PageTitle sub="Course material the tutor can cite.">Library</PageTitle>

      <section aria-labelledby="src-h" className="space-y-3">
        <h2 id="src-h" className="text-lg font-semibold">
          Sources
        </h2>
        {sources.loading && <Loading />}
        <ErrorNote message={sources.error} />
        {data && <SourceTable sources={data} />}
      </section>

      <Card className="max-w-md">
        <label htmlFor="token" className="mb-1 block text-sm font-medium">
          Admin token
        </label>
        <input
          id="token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className={FIELD}
        />
        <p className="mt-1 text-xs text-muted">Needed to add sources. Kept in memory only.</p>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <UploadForm token={token} onDone={reload} />
        <UrlForm token={token} onDone={reload} />
      </div>
    </div>
  );
}

function SourceTable({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return <p className="text-sm text-muted">No sources yet.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <caption className="sr-only">Ingested sources</caption>
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Title</th>
            <th scope="col" className="px-3 py-2 font-medium">Type</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">Units</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {sources.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2">{s.title}</td>
              <td className="px-3 py-2">{s.modality}</td>
              <td className="px-3 py-2">
                <Badge tone={TONE[s.status]}>{s.status}</Badge>
                {s.error && <p className="mt-1 text-xs text-bad">{s.error}</p>}
              </td>
              <td className="px-3 py-2 text-right">{s.units}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type FormProps = { token: string; onDone: () => void };

function useSubmit(token: string, onDone: () => void) {
  const [state, setState] = useState<{ busy: boolean; error: string | null; ok: string | null }>({
    busy: false,
    error: null,
    ok: null,
  });
  async function run(job: () => Promise<{ source_id: string }>, form: HTMLFormElement) {
    if (!token) return setState({ busy: false, error: "Enter the admin token first.", ok: null });
    setState({ busy: true, error: null, ok: null });
    try {
      const { source_id } = await job();
      form.reset();
      setState({ busy: false, error: null, ok: `Queued (${source_id}).` });
      onDone();
    } catch (e) {
      setState({ busy: false, error: adminError(e), ok: null });
    }
  }
  return { ...state, run };
}

function Status({ error, ok }: { error: string | null; ok: string | null }) {
  return (
    <>
      <ErrorNote message={error} />
      {ok && (
        <p role="status" className="text-sm text-good">
          {ok}
        </p>
      )}
    </>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

function UploadForm({ token, onDone }: FormProps) {
  const { busy, error, ok, run } = useSubmit(token, onDone);
  return (
    <Card>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const data = new FormData(form);
          if (!data.get("license")) data.delete("license");
          if (!data.get("pages")) data.delete("pages");
          run(() => api.uploadSource(data, token), form);
        }}
        className="space-y-3"
      >
        <h2 className="font-semibold">Upload PDF or slides</h2>
        <Field id="up-file" label="File">
          <input id="up-file" name="file" type="file" accept="application/pdf,.pdf,.pptx" required className={FIELD} />
        </Field>
        <Field id="up-title" label="Title">
          <input id="up-title" name="title" required className={FIELD} />
        </Field>
        <Field id="up-kind" label="Kind">
          <select id="up-kind" name="kind" defaultValue="pdf" className={FIELD}>
            <option value="pdf">PDF (textbook)</option>
            <option value="slides">Slides</option>
          </select>
        </Field>
        <Field id="up-license" label="License (optional)">
          <input id="up-license" name="license" className={FIELD} />
        </Field>
        <Field id="up-pages" label="Pages (optional)">
          <input id="up-pages" name="pages" placeholder="1-60" pattern="[0-9,\- ]*" className={FIELD} />
        </Field>
        <Status error={error} ok={ok} />
        <Button type="submit" disabled={busy}>
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </form>
    </Card>
  );
}

function UrlForm({ token, onDone }: FormProps) {
  const { busy, error, ok, run } = useSubmit(token, onDone);
  return (
    <Card>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const f = new FormData(form);
          const license = String(f.get("license") ?? "").trim();
          run(
            () =>
              api.addUrlSource(
                { url: String(f.get("url")), title: String(f.get("title")), ...(license && { license }) },
                token,
              ),
            form,
          );
        }}
        className="space-y-3"
      >
        <h2 className="font-semibold">Add YouTube lecture</h2>
        <Field id="yt-url" label="Video URL">
          <input id="yt-url" name="url" type="url" required placeholder="https://www.youtube.com/watch?v=…" className={FIELD} />
        </Field>
        <Field id="yt-title" label="Title">
          <input id="yt-title" name="title" required className={FIELD} />
        </Field>
        <Field id="yt-license" label="License (optional)">
          <input id="yt-license" name="license" className={FIELD} />
        </Field>
        <Status error={error} ok={ok} />
        <Button type="submit" disabled={busy}>
          {busy ? "Adding…" : "Add lecture"}
        </Button>
      </form>
    </Card>
  );
}
