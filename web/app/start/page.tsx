"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorNote, FIELD, Loading, PageTitle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { saveStudentId, sessionSet, useStoredStudentId } from "@/lib/student";
import { useApi } from "@/lib/useApi";

const LEVELS = [
  { value: 0, label: "New to it" },
  { value: 1, label: "Heard of it" },
  { value: 2, label: "Comfortable" },
] as const;

const DIAGNOSTIC_QUESTIONS = 10;

export default function StartPage() {
  const router = useRouter();
  const concepts = useApi(api.concepts, "concepts");
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [examDate, setExamDate] = useState("");
  const [familiarity, setFamiliarity] = useState<Record<string, 0 | 1 | 2>>({});
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasProfile = Boolean(useStoredStudentId());

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setStep("Creating your profile");
      const { student_id } = await api.createStudent(name.trim() || undefined);
      saveStudentId(student_id);
      setStep("Saving what you already know");
      await api.intake(student_id, {
        goal: goal.trim() || undefined,
        exam_date: examDate || undefined,
        familiarity,
      });
      setStep("Preparing your diagnostic");
      const assessment = await api.createAssessment({
        student_id,
        kind: "diagnostic",
        scope: [],
        n: DIAGNOSTIC_QUESTIONS,
      });
      sessionSet(`assessment:${assessment.assessment_id}`, assessment.questions);
      router.push(`/assess/run?id=${encodeURIComponent(assessment.assessment_id)}`);
    } catch (err) {
      setError(errorMessage(err));
      setStep(null);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageTitle sub="A few quick questions so the first quiz starts at the right level.">Welcome</PageTitle>
      {hasProfile && (
        <p className="mb-4 rounded-lg bg-soft px-3 py-2 text-sm">
          You already have a profile on this device. <Link href="/" className="underline">Back to the tutor</Link>, or
          continue below to start over with a new profile.
        </p>
      )}
      <form onSubmit={submit} className="space-y-6">
        <Card className="space-y-4">
          <div>
            <label htmlFor="name" className="mb-1 block text-sm font-medium">
              Name <span className="text-muted">(optional)</span>
            </label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" className={FIELD} />
          </div>
          <div>
            <label htmlFor="goal" className="mb-1 block text-sm font-medium">
              Goal <span className="text-muted">(optional)</span>
            </label>
            <input
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Pass the end-semester exam"
              className={FIELD}
            />
          </div>
          <div>
            <label htmlFor="exam" className="mb-1 block text-sm font-medium">
              Exam date <span className="text-muted">(optional)</span>
            </label>
            <input id="exam" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} className={FIELD} />
          </div>
        </Card>

        <section aria-labelledby="fam-title" className="space-y-3">
          <h2 id="fam-title" className="text-lg font-semibold">
            How familiar are you with each topic?
          </h2>
          {concepts.loading && <Loading label="Loading topics" />}
          <ErrorNote message={concepts.error} />
          {concepts.data?.topics.map((t) => (
            <Card key={t.id}>
              <fieldset>
                <legend className="mb-2 font-medium">{t.name}</legend>
                <div className="grid grid-cols-3 gap-2">
                  {LEVELS.map((l) => (
                    <label
                      key={l.value}
                      className="flex min-h-10 cursor-pointer items-center justify-center rounded-lg border border-line px-2 py-2 text-center text-sm has-[:checked]:border-accent has-[:checked]:bg-accent/10 has-[:checked]:font-medium has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent"
                    >
                      <input
                        type="radio"
                        name={`fam-${t.id}`}
                        value={l.value}
                        checked={familiarity[t.id] === l.value}
                        onChange={() => setFamiliarity((f) => ({ ...f, [t.id]: l.value }))}
                        className="sr-only"
                      />
                      {l.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            </Card>
          ))}
        </section>

        <ErrorNote message={error} />
        <Button type="submit" disabled={step !== null || concepts.loading}>
          {step ? `${step}…` : "Start diagnostic"}
        </Button>
      </form>
    </div>
  );
}
