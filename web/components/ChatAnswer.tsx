"use client";

import { useState } from "react";
import { api, errorMessage, type ChatResponse, type Citation, type Feedback, type Question } from "@/lib/api";
import { citationsById } from "@/lib/util";
import { useStudent } from "@/lib/student";
import { CitationChip } from "./CitationChip";
import { FeedbackCard } from "./FeedbackCard";
import { QuestionCard } from "./QuestionCard";
import { ErrorNote } from "./ui";

type Props = { response: ChatResponse; lang: "en" | "hi"; onCite: (c: Citation) => void };

export function ChatAnswer({ response, lang, onCite }: Props) {
  const byId = citationsById(response.citations);
  return (
    <div lang={lang} className="space-y-3">
      {response.declined ? (
        <div className="rounded-xl border border-warn/50 bg-warn/10 p-3 text-sm">
          <p className="mb-1 font-medium text-warn">Not covered in your course material</p>
          <p>{response.message}</p>
        </div>
      ) : (
        <p className="leading-relaxed">
          {response.sentences.map((s, i) => (
            <span key={i}>
              {s.text}
              {[...new Set(s.cites)].map((id) => {
                const c = byId.get(id);
                return c ? <CitationChip key={id} citation={c} onOpen={onCite} /> : null;
              })}{" "}
            </span>
          ))}
        </p>
      )}
      {response.outside.length > 0 && (
        <section className="rounded-xl border border-dashed border-line bg-soft p-3 text-sm">
          <h3 className="mb-1 font-medium">Outside your material (not from your course sources)</h3>
          <ul className="list-disc space-y-1 pl-5">
            {response.outside.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
        </section>
      )}
      {response.check_question && <CheckQuestion question={response.check_question} onCite={onCite} />}
    </div>
  );
}

function CheckQuestion({ question, onCite }: { question: Question; onCite: (c: Citation) => void }) {
  const studentId = useStudent();
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(response: string) {
    setBusy(true);
    setError(null);
    try {
      setFeedback(await api.chatCheck({ student_id: studentId, question_id: question.question_id, response }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <QuestionCard question={question} onSubmit={submit} busy={busy} locked={feedback !== null} heading="Quick check" />
      <ErrorNote message={error} />
      {feedback && <FeedbackCard feedback={feedback} onCite={onCite} />}
    </div>
  );
}
