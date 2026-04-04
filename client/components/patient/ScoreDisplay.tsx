import { NeoCard } from "@/components/ui/NeoCard";

interface Score {
  final_score?: number;
  pass_fail?: string;
  adaptive_decision?: string;
  word_accuracy?: number;
  phoneme_accuracy?: number;
  fluency_score?: number;
  speech_rate_wpm?: number;
  dominant_emotion?: string;
  engagement_score?: number;
  asr_transcript?: string;
  performance_level?: string;
}

export function ScoreDisplay({ score }: { score: Score }) {
  const isPassed = score.pass_fail === "pass";
  return (
    <div className="space-y-4 animate-pop-in">
      <NeoCard accent={isPassed ? "secondary" : "accent"} className="text-center space-y-2">
        <div className="text-5xl font-black">
          {score.final_score?.toFixed(1)}
          <span className="text-xl">/100</span>
        </div>
        <div className="font-black uppercase text-lg">{isPassed ? "PASS" : "FAIL"}</div>
        {score.adaptive_decision && (
          <div className="text-sm font-bold border-2 border-black inline-block px-3 py-1 uppercase">
            {score.adaptive_decision === "advance"
              ? "⬆ Level Up!"
              : score.adaptive_decision === "drop"
              ? "⬇ Level Down"
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
            ["Engagement", score.engagement_score],
            ["Emotion", score.dominant_emotion],
          ] as [string, number | string | undefined][]
        ).map(([label, value]) => (
          <div key={label}>
            <p className="font-black uppercase text-xs text-gray-500">{label}</p>
            <p className="font-bold">
              {typeof value === "number" ? `${value.toFixed(1)}%` : String(value ?? "—")}
            </p>
          </div>
        ))}
      </NeoCard>

      {score.asr_transcript && (
        <NeoCard className="space-y-1">
          <p className="font-black uppercase text-xs">Your Transcript</p>
          <p className="font-medium italic">&quot;{score.asr_transcript}&quot;</p>
        </NeoCard>
      )}
    </div>
  );
}
