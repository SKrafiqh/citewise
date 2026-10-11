"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { FeedbackCard } from "@/components/FeedbackCard";
import { QuestionCard } from "@/components/QuestionCard";
import { SourceModal } from "@/components/SourceViewer";
import { Button, Card, ErrorNote, Loading, PageTitle } from "@/components/ui";
import { ApiError, api, errorMessage, type Citation, type Feedback, type Question } from "@/lib/api";
import { useSessionJson } from "@/lib/student";

export default function RunPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Run />
    </Suspense>
  );
}

function Run() {
  const id = useSearchParams().get("id");
  const questions = useSessionJson<Question[]>(`assessment:${id}`);
  if (!id) return <ErrorNote message="Missing assessment id." />;
  if (questions === undefined) return <Loading />;
  if (!questions || questions.length === 0) {
    return (
      <Card className="space-y-2">
        <p>The questions for this assessment are not stored in this browser session.</p>
        <p className="text-sm text-muted">
          <Link href="/assess" className="underline">
            Start a new assessment
          </Link>{" "}
          or <Link href={`/assess/report?id=${encodeURIComponent(id)}`} className="underline">view its report</Link>.
        </p>
      </Card>
    );
  }
  return <Player id={id} questions={questions} />;
}

function Player({ id, questions }: { id: string; questions: Question[] }) {
  const [idx, setIdx] = useState(0);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Citation | null>(null);
  const done = idx >= questions.length;
  const question = questions[idx];

  const advance = () => {
    setFeedback(null);
    setError(null);
    setIdx((i) => i + 1);
  };

  async function submit(response: string) {
    setBusy(true);
    setError(null);
    try {
      setFeedback(await api.answer(id, { question_id: question.question_id, response }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) advance();
      else setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <PageTitle>All done</PageTitle>
        <Link
          href={`/assess/report?id=${encodeURIComponent(id)}`}
          className="inline-flex min-h-10 items-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg"
        >
          See your report
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle>
        Question {idx + 1} of {questions.length}
      </PageTitle>
      <progress className="sr-only" max={questions.length} value={idx} aria-label="Progress" />
      <QuestionCard key={question.question_id} question={question} onSubmit={submit} busy={busy} locked={feedback !== null} />
      <ErrorNote message={error} />
      {feedback && (
        <>
          <FeedbackCard feedback={feedback} onCite={setOpen} />
          <Button onClick={advance} autoFocus>
            {idx + 1 < questions.length ? "Next question" : "Finish"}
          </Button>
        </>
      )}
      <SourceModal citation={open} onClose={() => setOpen(null)} />
    </div>
  );
}
