import type { Citation, Feedback } from "@/lib/api";
import { pct } from "@/lib/util";
import { CitationList } from "./CitationChip";
import { Card } from "./ui";

export function FeedbackCard({ feedback, onCite }: { feedback: Feedback; onCite: (c: Citation) => void }) {
  const { correct } = feedback;
  const delta = Math.round(feedback.mastery_delta * 100);
  return (
    <Card className={correct ? "border-good/50" : "border-bad/50"}>
      <div role="status" className="space-y-2 text-sm">
        <p className={`text-base font-semibold ${correct ? "text-good" : "text-bad"}`}>
          {correct ? "✓ Correct" : "✗ Not quite"}
        </p>
        <p>
          <span className="font-medium">Answer:</span> {feedback.correct_answer}
        </p>
        <p>{feedback.explanation}</p>
        {feedback.misconception && (
          <p className="rounded-lg bg-warn/10 px-3 py-2 text-warn">
            <span className="font-medium">Common misconception:</span> {feedback.misconception}
          </p>
        )}
        <CitationList citations={feedback.citations} onOpen={onCite} />
        <p className="text-muted">
          Mastery {pct(feedback.p_before)} → {pct(feedback.p_after)} ({delta >= 0 ? "+" : ""}
          {delta} pts)
        </p>
      </div>
    </Card>
  );
}
