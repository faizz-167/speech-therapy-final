import type { AttemptScore } from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatEmotion(value: string | null | undefined): string {
  if (!value) return "Neutral";
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
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
  if (score.pass_fail === "pass") {
    const s = score.final_score ?? 0;
    return s >= 80 ? "Excellent work!" : "Well done!";
  }
  return "Keep going — you've got this.";
}

function getDecisionLabel(score: AttemptScore): { label: string; accent: string } {
  if (!score.adaptive_decision) return { label: "", accent: "" };
  if (isDistressEmotion(score) && score.adaptive_decision === "stay") {
    return { label: "Take a breath ✦", accent: "bg-neo-muted" };
  }
  return score.adaptive_decision === "advance"
    ? { label: "Level Up! ↑", accent: "bg-neo-secondary" }
    : score.adaptive_decision === "drop"
      ? { label: "Adjusting level ↓", accent: "bg-neo-accent" }
      : { label: "Keep going →", accent: "bg-white" };
}

function getEmotionIcon(emotion: string | null | undefined): string {
  const e = (emotion ?? "").toLowerCase();
  if (e === "happy" || e === "excited") return "😊";
  if (e === "neutral") return "😐";
  if (e === "surprised") return "😮";
  if (e === "sad") return "😔";
  if (e === "angry") return "😤";
  if (e === "fearful") return "😰";
  return "😶";
}

// ---------------------------------------------------------------------------
// Client-side feedback — mirrors backend pools, used as fallback when
// friendly_feedback is null (e.g. old attempts scored before the field existed)
// ---------------------------------------------------------------------------

const FEEDBACK: Record<string, string[]> = {
  distress_angry: [
    "You did the work and that takes real courage. Take a breath before the next one.",
    "It's okay to feel frustrated — speech practice is genuinely hard. Let's reset and go again.",
    "You're still here and still trying. That's what matters most right now.",
    "Take a moment. When you're ready, the next attempt is waiting for you.",
  ],
  distress_sad: [
    "You're still making progress, even when it doesn't feel that way.",
    "Let's keep the next step gentle. You showed up today and that counts.",
    "It's okay to have a tough session. The effort you're putting in is real.",
    "You don't have to be perfect — you just have to keep going. And you are.",
  ],
  pass_high: [
    "Excellent! That was a strong, confident response.",
    "You nailed it — that kind of clarity is exactly what we're working toward.",
    "That's the result of real practice. Well done!",
    "Brilliant work. Your consistency is really showing.",
  ],
  pass_moderate: [
    "Good job! You're making steady progress.",
    "That worked well — you're finding your rhythm.",
    "Nice effort. Every attempt adds up and you're moving forward.",
    "Well done — keep that energy for the next one.",
  ],
  fail_gentle: [
    "So close! A small adjustment and you'll get there.",
    "That one was tricky — let's try it again together.",
    "No worries — this is exactly what practice is for. Go again!",
    "Keep going. Each attempt is teaching you something new.",
  ],
  fail_struggling: [
    "This is genuinely hard work, and you're still showing up. That matters.",
    "Don't be hard on yourself — learning takes time and you're doing it.",
    "It's okay if this is tough right now. Take a breath and we'll go again.",
    "Progress isn't always linear. You're still here, and that's everything.",
  ],
  no_speech: [
    "We didn't quite catch that — make sure the mic is clear and try again!",
    "No audio picked up this time. Ready to give it another go?",
    "Looks like something went quiet there. Take a moment and try again.",
  ],
  advance: [
    "You've levelled up — your hard work earned it!",
    "Moving to the next challenge! You've shown real mastery here.",
  ],
  drop: [
    "We're finding the level that fits best — that's smart practice.",
    "Let's build confidence at a slightly easier level. You've got this.",
  ],
};

function pickFeedback(pool: string[]): string {
  return pool[Math.floor(Math.random() * pool.length)];
}

function getClientFeedback(score: AttemptScore): string {
  const emotion = (score.dominant_emotion ?? "").toLowerCase();
  const eScore = typeof score.emotion_score === "number" ? score.emotion_score : 100;
  const finalScore = score.final_score ?? 0;

  // No-speech path
  if (score.pass_fail === "fail" && finalScore === 0 && !score.asr_transcript) {
    return pickFeedback(FEEDBACK.no_speech);
  }

  // Distress overrides
  if ((emotion === "angry" || emotion === "fearful") && eScore <= 40) {
    return pickFeedback(FEEDBACK.distress_angry);
  }
  if (emotion === "sad" && eScore <= 55) {
    return pickFeedback(FEEDBACK.distress_sad);
  }

  // Level decisions
  if (score.adaptive_decision === "advance") {
    return pickFeedback(FEEDBACK.advance);
  }
  if (score.adaptive_decision === "drop") {
    return pickFeedback(FEEDBACK.drop);
  }

  if (score.pass_fail === "pass") {
    return pickFeedback(finalScore >= 80 ? FEEDBACK.pass_high : FEEDBACK.pass_moderate);
  }

  const isStruggling = finalScore < 45 || ["sad", "angry", "fearful"].includes(emotion);
  return pickFeedback(isStruggling ? FEEDBACK.fail_struggling : FEEDBACK.fail_gentle);
}

// ---------------------------------------------------------------------------
// ScoreBar
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ScoreDisplay({ score }: { score: AttemptScore }) {
  const isPassed = score.pass_fail === "pass";
  const emotionLabel = formatEmotion(score.dominant_emotion);
  const distress = isDistressEmotion(score);
  const decision = getDecisionLabel(score);

  // Use backend-generated message when available; fall back to client-side generation
  const feedbackMsg = score.friendly_feedback ?? getClientFeedback(score);

  const feedbackBg = distress
    ? "bg-neo-muted border-neo-black"
    : isPassed
      ? "bg-neo-secondary border-neo-black"
      : "bg-white border-neo-black";

  const feedbackIcon = distress ? "🤝" : isPassed ? "🌟" : "💪";

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

      {/* ── FEEDBACK MESSAGE — always shown, always emotion-aware ── */}
      <div className={`border-4 shadow-neo-sm px-5 py-4 flex items-start gap-4 ${feedbackBg}`}>
        <span className="text-3xl shrink-0 leading-none mt-0.5">{feedbackIcon}</span>
        <p className="font-bold text-base leading-relaxed">{feedbackMsg}</p>
      </div>

      {/* ── EMOTION CARD ── */}
      <div className={`border-4 border-neo-black shadow-neo-sm flex items-center justify-between gap-4 p-4 ${distress ? "bg-neo-accent" : "bg-white"}`}>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{getEmotionIcon(score.dominant_emotion)}</span>
          <div>
            <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/55 mb-0.5">How You Sounded</p>
            <p className="font-black text-xl">{emotionLabel}</p>
          </div>
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

      {/* ── TRANSCRIPT ── */}
      {score.asr_transcript && (
        <div className="border-4 border-neo-black bg-white px-4 py-3 space-y-1">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50">What We Heard</p>
          <p className="font-medium italic">&ldquo;{score.asr_transcript}&rdquo;</p>
        </div>
      )}
    </div>
  );
}
