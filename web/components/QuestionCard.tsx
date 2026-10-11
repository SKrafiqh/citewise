"use client";

import { useId, useState } from "react";
import type { Question } from "@/lib/api";
import { Button, Card, FIELD } from "./ui";

type Props = {
  question: Question;
  onSubmit: (response: string) => void;
  busy?: boolean;
  locked?: boolean;
  heading?: string;
};

export function QuestionCard({ question, onSubmit, busy = false, locked = false, heading }: Props) {
  const [value, setValue] = useState("");
  const name = useId();
  const disabled = busy || locked;
  const options = question.options ?? [];

  return (
    <Card>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) onSubmit(value.trim());
        }}
        className="space-y-3"
      >
        <fieldset disabled={disabled} className="space-y-3">
          <legend className="mb-2 w-full">
            {heading && <span className="block text-xs font-medium uppercase text-muted">{heading}</span>}
            <span className="block text-base font-medium">{question.stem}</span>
            <span className="block text-xs text-muted">{question.concept_name}</span>
          </legend>
          {question.qtype === "mcq" ? (
            <div className="space-y-2">
              {options.map((o) => (
                <label
                  key={o.key}
                  className="flex cursor-pointer items-start gap-2 rounded-lg border border-line px-3 py-2 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent/10"
                >
                  <input
                    type="radio"
                    name={name}
                    value={o.key}
                    checked={value === o.key}
                    onChange={() => setValue(o.key)}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium">{o.key}.</span> {o.text}
                  </span>
                </label>
              ))}
            </div>
          ) : question.qtype === "short" ? (
            <>
              <label htmlFor={`${name}-a`} className="sr-only">
                Your answer
              </label>
              <textarea
                id={`${name}-a`}
                rows={4}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Your answer"
                className={FIELD}
              />
            </>
          ) : (
            <>
              <label htmlFor={`${name}-a`} className="sr-only">
                Your numerical answer
              </label>
              <input
                id={`${name}-a`}
                type="text"
                inputMode="decimal"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Numerical answer"
                className={FIELD}
              />
            </>
          )}
        </fieldset>
        {!locked && (
          <Button type="submit" disabled={busy || !value.trim()}>
            {busy ? "Checking…" : "Submit answer"}
          </Button>
        )}
      </form>
    </Card>
  );
}
