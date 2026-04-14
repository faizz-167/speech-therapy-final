import { NeoCard } from "@/components/ui/NeoCard";
import type { AttemptScore } from "@/types";

export function ScoreDisplay({ score }: { score: AttemptScore }) {
  const isPassed = score.pass_fail === "pass";
  return (
    <div className="space-y-4 animate-pop-in">
      <NeoCard accent={isPassed ? "secondary" : "accent"} className="text-center space-y-2">
        {score.attempt_number ? (
          <div className="text-xs font-black uppercase text-neo-black/70">Attempt {score.attempt_number}</div>
        ) : null}
        <div className="text-5xl font-black">
          {score.final_score?.toFixed(1)}
          <span className="text-xl">/100</span>
        </div>
        <div className="font-black uppercase text-lg">
          {isPassed ? "✓ Great job!" : "↻ Not quite — keep going!"}
        </div>
        {score.adaptive_decision && (
          <div className="text-sm font-bold border-2 border-black inline-block px-3 py-1 uppercase">
            {score.adaptive_decision === "advance"
              ? "⬆ Level Up!"
              : score.adaptive_decision === "drop"
              ? "⬇ Adjusting to easier level"
              : "→ Stay"}
          </div>
        )}
      </NeoCard>

      <NeoCard className="grid grid-cols-2 gap-3 text-sm">
        {(
          [
            ["Word Accuracy", score.word_accuracy],
            ["Phoneme Accuracy", score.phoneme_accuracy],
            ["Fluency Score", score.fluency_score],
            ["Speech Rate (WPM)", score.speech_rate_wpm],
            ["Speech Rate Score", score.speech_rate_score],
            ["Confidence", score.confidence_score],
            ["Emotion Score", score.emotion_score],
            ["Engagement", score.engagement_score],
            ["Dominant Emotion", score.dominant_emotion],
          ] as [string, number | string | undefined][]
        ).map(([label, value]) => (
          <div key={label}>
            <p className="font-black uppercase text-xs text-neo-black/70">{label}</p>
            <p className="font-bold">
              {typeof value === "number"
                ? label === "Speech Rate (WPM)"
                  ? value.toFixed(1)
                  : `${value.toFixed(1)}%`
                : String(value ?? "—")}
            </p>
          </div>
        ))}
      </NeoCard>

      {score.review_recommended && (
        <NeoCard accent="accent" className="space-y-1">
          <p className="font-black uppercase text-xs">Review Recommended</p>
          <p className="font-medium">
            {score.fail_reason ?? "The transcript or scoring inputs look unreliable. Please retry this prompt."}
          </p>
        </NeoCard>
      )}

      {score.asr_transcript && (
        <NeoCard className="space-y-1">
          <p className="font-black uppercase text-xs">ASR Transcript</p>
          <p className="font-medium italic">&quot;{score.asr_transcript}&quot;</p>
        </NeoCard>
      )}
    </div>
  );
}
