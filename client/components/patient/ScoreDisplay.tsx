import type { AttemptScore } from "@/types";

function formatEmotion(value: string | null | undefined): string {
  if (!value) return "Waiting for emotion";
  return value.replace(/_/g, " ");
}

function isDistressEmotion(score: AttemptScore): boolean {
  const emotion = (score.dominant_emotion ?? "").toLowerCase();
  const emotionScore = typeof score.emotion_score === "number" ? score.emotion_score : null;
  if (emotionScore === null) return false;
  if ((emotion === "angry" || emotion === "fearful") && emotionScore <= 40) return true;
  if (emotion === "sad" && emotionScore <= 55) return true;
  return false;
}

function getHeadline(score: AttemptScore): string {
  const emotion = (score.dominant_emotion ?? "").toLowerCase();
  if (isDistressEmotion(score)) {
    if (emotion === "angry" || emotion === "fearful") return "Let's pause and reset.";
    if (emotion === "sad") return "Let's go gently from here.";
  }
  return score.pass_fail === "pass" ? "Great work." : "Keep going.";
}

function getDecisionLabel(score: AttemptScore): { label: string; accent: string } {
  if (!score.adaptive_decision) return { label: "", accent: "" };
  if (isDistressEmotion(score) && score.adaptive_decision === "stay") {
    return { label: "Stay & Reset", accent: "bg-neo-muted" };
  }
  return score.adaptive_decision === "advance"
    ? { label: "Level Up! ↑", accent: "bg-neo-secondary" }
    : score.adaptive_decision === "drop"
      ? { label: "Adjusting Level ↓", accent: "bg-neo-accent" }
      : { label: "Stay", accent: "bg-white" };
}

function ScoreBar({ label, value, accent = "bg-neo-accent" }: { label: string; value: number | string | null | undefined; accent?: string }) {
  const numVal = typeof value === "number" ? value : null;
  const pct = numVal != null ? Math.min(100, Math.max(0, numVal)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/55">{label}</p>
        <p className="font-black text-xs">
          {numVal != null ? (label.includes("WPM") ? numVal.toFixed(1) : `${numVal.toFixed(1)}%`) : String(value ?? "—")}
        </p>
      </div>
      <div className="h-2.5 border-2 border-neo-black bg-neo-bg overflow-hidden">
        <div
          className={`h-full ${accent} animate-bar-grow`}
          style={{ "--bar-target": `${pct}%` } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

export function ScoreDisplay({ score }: { score: AttemptScore }) {
  const isPassed = score.pass_fail === "pass";
  const emotionLabel = formatEmotion(score.dominant_emotion);
  const distress = isDistressEmotion(score);
  const decision = getDecisionLabel(score);

  return (
    <div className="space-y-4 animate-pop-in">

      {/* ── BIG SCORE ── */}
      <div className={`border-4 border-neo-black shadow-neo-md ${distress ? "bg-neo-muted" : isPassed ? "bg-neo-secondary" : "bg-neo-accent"}`}>
        {score.attempt_number != null && (
          <div className="border-b-4 border-neo-black px-4 py-2 bg-neo-black text-white font-black uppercase text-xs tracking-widest">
            Attempt {score.attempt_number} of {3}
          </div>
        )}
        <div className="p-6 text-center space-y-2">
          <div className="text-7xl font-black leading-none animate-score-slam">
            {score.final_score?.toFixed(1)}<span className="text-2xl opacity-50">/100</span>
          </div>
          <p className="font-black uppercase text-xl tracking-tight">{getHeadline(score)}</p>
          {decision.label && (
            <div className={`inline-block border-4 border-neo-black px-4 py-1 font-black uppercase text-sm tracking-widest mt-2 ${decision.accent} shadow-neo-sm`}>
              {decision.label}
            </div>
          )}
        </div>
      </div>

      {/* ── EMOTION CARD ── */}
      <div className={`border-4 border-neo-black shadow-neo-sm flex items-center justify-between gap-4 p-4 ${distress ? "bg-neo-accent" : "bg-white"}`}>
        <div>
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/55 mb-0.5">Detected Emotion</p>
          <p className="font-black text-xl capitalize">{emotionLabel}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/55 mb-0.5">Emotion Score</p>
          <p className="font-black text-xl">
            {typeof score.emotion_score === "number" ? `${score.emotion_score.toFixed(1)}%` : "—"}
          </p>
        </div>
      </div>

      {/* ── METRIC BARS ── */}
      <div className="border-4 border-neo-black bg-white shadow-neo-sm p-5 space-y-3">
        <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 border-b-2 border-neo-black/10 pb-2 mb-3">Detailed Metrics</p>
        <ScoreBar label="Word Accuracy" value={score.word_accuracy} accent="bg-neo-secondary" />
        <ScoreBar label="Phoneme Accuracy" value={score.phoneme_accuracy} accent="bg-neo-muted" />
        <ScoreBar label="Fluency Score" value={score.fluency_score} accent="bg-neo-accent" />
        <ScoreBar label="Confidence" value={score.confidence_score} accent="bg-neo-secondary" />
        <ScoreBar label="Engagement" value={score.engagement_score} accent="bg-neo-muted" />
        <div className="border-t-2 border-neo-black/10 pt-3 grid grid-cols-2 gap-3">
          <div className="border-2 border-neo-black bg-neo-bg px-3 py-2 text-center">
            <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">Speech Rate</p>
            <p className="font-black text-base">{score.speech_rate_wpm != null ? `${(score.speech_rate_wpm as number).toFixed(1)} wpm` : "—"}</p>
          </div>
          <div className="border-2 border-neo-black bg-neo-bg px-3 py-2 text-center">
            <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">Emotion Score</p>
            <p className="font-black text-base">{typeof score.emotion_score === "number" ? `${score.emotion_score.toFixed(1)}%` : "—"}</p>
          </div>
        </div>
      </div>

      {/* ── REVIEW NOTE ── */}
      {score.review_recommended && (
        <div className="border-4 border-neo-black bg-neo-accent px-4 py-3 space-y-1">
          <p className="font-black uppercase text-xs tracking-widest">Review Recommended</p>
          <p className="font-medium text-sm">{score.fail_reason ?? "The scoring inputs look unreliable. Please retry this prompt."}</p>
        </div>
      )}

      {/* ── TRANSCRIPT ── */}
      {score.asr_transcript && (
        <div className="border-4 border-neo-black bg-white px-4 py-3 space-y-1">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50">ASR Transcript</p>
          <p className="font-medium italic">&ldquo;{score.asr_transcript}&rdquo;</p>
        </div>
      )}
    </div>
  );
}
