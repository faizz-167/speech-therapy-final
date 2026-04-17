"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { createWebSocket, WebSocketHandle } from "@/lib/ws";
import { AttemptScore, PollResult, RecordingMeta, SessionPhase, TaskExerciseState } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { Recorder } from "@/components/patient/Recorder";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const NO_SPEECH_REASON = "No speech detected";
const MAX_ATTEMPTS = 3;
const UPLOAD_TIMEOUT_MS = 30_000;
const ANALYSIS_TIMEOUT_MS = 90_000;

function isDistressScore(score: AttemptScore | null): boolean {
  if (!score) return false;
  const emotion = (score.dominant_emotion ?? "").toLowerCase();
  const emotionScore = typeof score.emotion_score === "number" ? score.emotion_score : null;
  if (emotionScore === null) return false;
  if ((emotion === "angry" || emotion === "fearful") && emotionScore <= 40) return true;
  if (emotion === "sad" && emotionScore <= 55) return true;
  return false;
}

function getSupportMessage(score: AttemptScore | null): string {
  const emotion = (score?.dominant_emotion ?? "").toLowerCase();
  if (emotion === "angry" || emotion === "fearful") return "You did the speech work. Let's slow down for a moment before continuing.";
  if (emotion === "sad") return "You are still making progress. Let's keep the next step gentle.";
  return "Let's take the next step calmly.";
}

/* Animated analysis spinner */
function AnalysisSpinner({ label }: { label: string }) {
  return (
    <div className="py-10 space-y-6 text-center">
      {/* Waveform bars */}
      <div className="flex items-center justify-center gap-1.5 h-12">
        {Array.from({ length: 7 }, (_, i) => (
          <div
            key={i}
            className={`w-3 bg-neo-accent border-2 border-neo-black animate-wave-${i + 1}`}
            style={{ height: "40px", transformOrigin: "bottom" }}
          />
        ))}
      </div>
      <p className="font-black uppercase tracking-widest text-lg">{label}</p>
      <p className="text-sm font-medium text-neo-black/60">This may take 10–30 seconds</p>
    </div>
  );
}

/* Instruction phase: animated "listen then speak" UI */
function InstructionPanel({ prompt, onPlay }: {
  prompt: { instruction?: string | null; display_content?: string | null };
  onPlay: () => void;
}) {
  return (
    <div className="space-y-5 animate-fade-up">
      {/* Prompt content */}
      {prompt.display_content && (
        <div className="border-8 border-neo-black bg-neo-secondary shadow-neo-lg p-6 text-center">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-3">Say This</p>
          <p className="text-3xl md:text-4xl font-black tracking-tight leading-tight">{prompt.display_content}</p>
        </div>
      )}

      {/* Instruction text */}
      {prompt.instruction && (
        <div className="border-4 border-neo-black bg-white px-5 py-4">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-2">Instructions</p>
          <p className="font-bold text-base leading-relaxed">{prompt.instruction}</p>
        </div>
      )}

      {/* CTA */}
      <div className="border-4 border-neo-black bg-neo-muted/30 px-5 py-4 flex items-center gap-4">
        <div className="w-10 h-10 border-4 border-neo-black bg-white flex items-center justify-center font-black text-lg shrink-0">▶</div>
        <div className="flex-1">
          <p className="font-bold text-sm">Press the button to hear the instruction, then record your response.</p>
        </div>
      </div>

      <NeoButton onClick={onPlay} className="w-full text-base py-5" size="lg">
        ▶ Play Instruction &amp; Start
      </NeoButton>
    </div>
  );
}

/* Record phase: show prompt prominently */
function RecordPanel({ prompt, onRecording }: {
  prompt: { instruction?: string | null; display_content?: string | null };
  onRecording: (blob: Blob, meta: RecordingMeta) => void;
}) {
  return (
    <div className="space-y-5 animate-slide-right">
      {/* Prominent prompt */}
      {prompt.display_content && (
        <div className="border-8 border-neo-black bg-neo-secondary shadow-neo-lg p-6 text-center animate-pop-in">
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-3">Say This</p>
          <p className="text-3xl md:text-4xl font-black tracking-tight leading-tight">{prompt.display_content}</p>
        </div>
      )}

      {prompt.instruction && (
        <div className="border-4 border-neo-black bg-white px-5 py-3">
          <p className="font-medium text-sm leading-relaxed text-neo-black/70">{prompt.instruction}</p>
        </div>
      )}

      {/* Recording UI */}
      <div className="border-4 border-neo-black bg-white shadow-neo-sm">
        <div className="bg-neo-black text-white px-4 py-2 font-black uppercase tracking-widest text-xs flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-neo-accent rounded-full animate-pulse-ring inline-block"></span>
          Record Your Response
        </div>
        <div className="p-4">
          <Recorder onRecordingComplete={onRecording} disabled={false} />
        </div>
      </div>
    </div>
  );
}

export default function ExercisePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const router = useRouter();
  const userId = useAuthStore((state) => state.userId);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);

  const [phase, setPhase] = useState<SessionPhase>("instruction");
  const [score, setScore] = useState<AttemptScore | null>(null);
  const [attemptNumber, setAttemptNumber] = useState<number | null>(null);
  const [noSpeech, setNoSpeech] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [wsFallback, setWsFallback] = useState(false);

  const wsRef = useRef<WebSocketHandle | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentAttemptIdRef = useRef<string | null>(null);
  const autoCompletingRef = useRef(false);

  const { data: exerciseState, isLoading, error, refetch } = useQuery<TaskExerciseState>({
    queryKey: ["exercise", "state", assignmentId],
    queryFn: () => api.get<TaskExerciseState>(`/patient/tasks/${assignmentId}/session-state`),
    retry: false,
  });

  const currentPrompt = exerciseState?.current_prompt ?? null;
  const sessionId = exerciseState?.session_id ?? null;

  useEffect(() => {
    if (!bootstrapped || !userId) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      wsRef.current = createWebSocket(
        userId,
        (data) => {
          if (!currentAttemptIdRef.current || data.attempt_id !== currentAttemptIdRef.current) return;
          clearAttemptTracking();
          setWsReconnecting(false);
          if (data.adaptive_decision === "escalated") { toast.error("This task has been escalated for therapist review."); router.push("/patient/tasks"); return; }
          if (data.adaptive_decision === "alternate_prompt") { toast("Difficulty adjusted — trying a different exercise."); void finishOrAdvance(); return; }
          setNoSpeech(data.fail_reason === NO_SPEECH_REASON);
          setScore(data);
          setPhase("scored");
        },
        undefined,
        (attempt) => { setWsReconnecting(true); toast.info(`Reconnecting to score delivery... (attempt ${attempt}/${5})`); },
        () => { setWsReconnecting(false); setWsFallback(true); }
      );
    }, 0);
    return () => { cancelled = true; window.clearTimeout(timer); wsRef.current?.disconnect(); wsRef.current = null; clearAttemptTracking(); };
  }, [bootstrapped, userId]);

  useEffect(() => {
    if (!exerciseState) return;
    if (exerciseState.escalated) { toast.error("This task has been escalated for therapist review."); router.push("/patient/tasks"); return; }
    if (!exerciseState.current_prompt) return;
    setPhase("instruction"); setScore(null); setAttemptNumber(null); setNoSpeech(false); setUploadError("");
  }, [exerciseState?.escalated, exerciseState?.current_prompt?.prompt_id, router]);

  useEffect(() => {
    if (!exerciseState || exerciseState.current_prompt || !exerciseState.task_complete || autoCompletingRef.current) return;
    autoCompletingRef.current = true;
    void api.post(`/patient/tasks/${assignmentId}/complete`, {}).finally(() => { router.push("/patient/tasks"); });
  }, [assignmentId, exerciseState, router]);

  function clearAttemptTracking() {
    if (pollIntervalRef.current !== null) { clearInterval(pollIntervalRef.current); pollIntervalRef.current = null; }
    if (pollTimeoutRef.current !== null) { clearTimeout(pollTimeoutRef.current); pollTimeoutRef.current = null; }
    currentAttemptIdRef.current = null;
  }

  function playTTS() {
    if (!currentPrompt?.instruction) { setPhase("record"); return; }
    const utterance = new SpeechSynthesisUtterance(currentPrompt.instruction);
    utterance.onend = () => setPhase("record");
    speechSynthesis.speak(utterance);
  }

  async function finishOrAdvance() {
    clearAttemptTracking(); setScore(null); setAttemptNumber(null); setNoSpeech(false);
    const nextState = await refetch();
    const state = nextState.data;
    if (state?.current_prompt) { setPhase("instruction"); return; }
    try {
      const result = await api.post<{ message: string; status: string }>(`/patient/tasks/${assignmentId}/complete`, {});
      if (result.status === "pending") toast.info(result.message);
      router.push("/patient/tasks");
    } catch (completionError: unknown) {
      toast.error(completionError instanceof Error ? completionError.message : "Failed to finalize task.");
      router.push("/patient/tasks");
    }
  }

  function continueAfterAnalysisTimeout() {
    clearAttemptTracking(); setScore(null); setAttemptNumber(null); setNoSpeech(false);
    toast.info("Your task remains pending until the exercise result is ready.");
    router.push("/patient/tasks");
  }

  async function handleRecording(blob: Blob, meta: RecordingMeta) {
    if (!sessionId || !currentPrompt) return;
    setPhase("uploading"); setNoSpeech(false); setUploadError("");
    const form = new FormData();
    form.append("audio", blob, "recording.webm");
    form.append("prompt_id", currentPrompt.prompt_id);
    form.append("task_mode", currentPrompt.task_mode);
    form.append("prompt_type", currentPrompt.prompt_type);
    form.append("mic_activated_at", meta.micActivatedAt);
    if (meta.speechStartAt) form.append("speech_start_at", meta.speechStartAt);

    try {
      const response = await api.upload<{ attempt_id: string; attempt_number: number }>(`/session/${sessionId}/attempt`, form, { timeout: UPLOAD_TIMEOUT_MS });
      currentAttemptIdRef.current = response.attempt_id;
      setAttemptNumber(response.attempt_number);
      setPhase("scoring");

      pollIntervalRef.current = setInterval(async () => {
        try {
          const poll = await api.get<PollResult>(`/session/attempt/${response.attempt_id}`);
          if (poll.result && poll.result !== "pending" && poll.score) {
            clearAttemptTracking();
            if (poll.score.adaptive_decision === "escalated") { toast.error("This task has been escalated for therapist review."); router.push("/patient/tasks"); return; }
            if (poll.score.adaptive_decision === "alternate_prompt") { toast("Difficulty adjusted — trying a different exercise."); void finishOrAdvance(); return; }
            setNoSpeech(poll.score.fail_reason === NO_SPEECH_REASON);
            setScore(poll.score); setPhase("scored");
          }
        } catch { /* keep polling */ }
      }, 2000);

      pollTimeoutRef.current = setTimeout(() => {
        clearAttemptTracking();
        setPhase((currentPhase) => (currentPhase === "scoring" ? "analysis_timeout" : currentPhase));
      }, ANALYSIS_TIMEOUT_MS);
    } catch (recordingError: unknown) {
      clearAttemptTracking();
      if (recordingError instanceof Error && recordingError.name === "AbortError") {
        setUploadError("Upload timed out after 30 seconds. Please check your connection and try again.");
      } else {
        setUploadError(recordingError instanceof Error ? recordingError.message : "Upload failed. Please try again.");
      }
      setPhase("error");
    }
  }

  function retryExercise() {
    clearAttemptTracking(); setUploadError(""); setNoSpeech(false); setScore(null); setAttemptNumber(null); setPhase("instruction");
  }

  if (isLoading) return <LoadingState label="Loading exercise..." />;

  if (phase === "analysis_timeout") {
    return (
      <div className="animate-fade-up p-4 md:p-8 max-w-2xl mx-auto">
        <div className="border-4 border-neo-black bg-white shadow-neo-md p-8 text-center space-y-5">
          <div className="text-6xl">⏱️</div>
          <h2 className="text-2xl font-black uppercase tracking-tighter">Analysis Taking Longer Than Expected</h2>
          <p className="font-medium text-neo-black/70">Your recording was saved. This task stays pending until the result is reviewed.</p>
          <NeoButton className="w-full" onClick={continueAfterAnalysisTimeout}>Back to Tasks</NeoButton>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <ErrorState
        message={uploadError || (error instanceof Error ? error.message : "Something went wrong")}
        onRetry={currentPrompt ? retryExercise : () => router.refresh()}
      />
    );
  }

  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} onRetry={() => router.refresh()} />;

  if (!exerciseState || !currentPrompt) {
    return (
      <EmptyState
        icon="🎤"
        heading="No Active Exercise"
        subtext={exerciseState?.task_complete ? "This task is ready to be completed." : "No exercises are available right now for this task."}
        cta={{ label: "Back to Tasks", onClick: () => router.push("/patient/tasks") }}
      />
    );
  }

  const isWarmup = currentPrompt.prompt_type === "warmup";
  const terminalFailure = score?.pass_fail === "fail" && (score.attempt_number ?? attemptNumber ?? 0) >= MAX_ATTEMPTS;
  const canRetry = score?.pass_fail === "fail" && !terminalFailure;
  const needsSupportPause = isDistressScore(score);
  const currentProgress = Math.min(
    exerciseState.completed_prompts + (exerciseState.current_prompt ? 1 : 0),
    exerciseState.total_prompts
  );
  const progressPct = Math.round((currentProgress / exerciseState.total_prompts) * 100);

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-2xl mx-auto space-y-6">

      {/* ── HEADER ── */}
      <div className="border-b-4 border-neo-black pb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-black uppercase tracking-tighter">Exercise</h1>
            {isWarmup && (
              <span className="border-2 border-neo-black bg-neo-secondary px-2 py-0.5 text-xs font-black uppercase animate-pop-in">
                Warm-up
              </span>
            )}
            <span className="border-2 border-neo-black bg-white px-2 py-0.5 text-xs font-black uppercase">
              {exerciseState.current_level}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {wsReconnecting && (
              <span className="text-xs font-bold text-neo-accent border-2 border-neo-accent px-2 py-1 animate-pulse">⟳ Reconnecting</span>
            )}
            {wsFallback && !wsReconnecting && (
              <span className="text-xs font-bold text-neo-black/50 border-2 border-neo-black/30 px-2 py-1">Polling</span>
            )}
            {attemptNumber != null && (
              <span className="border-4 border-neo-black bg-neo-accent px-3 py-1 font-black text-sm">
                Attempt {attemptNumber}/{MAX_ATTEMPTS}
              </span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 border-2 border-neo-black bg-neo-bg overflow-hidden">
            <div
              className="h-full bg-neo-black transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="font-black text-sm whitespace-nowrap">{currentProgress}/{exerciseState.total_prompts}</span>
        </div>
      </div>

      {/* ── PHASE CONTENT ── */}

      {phase === "instruction" && currentPrompt && (
        <InstructionPanel prompt={currentPrompt} onPlay={playTTS} />
      )}

      {phase === "record" && currentPrompt && (
        <RecordPanel prompt={currentPrompt} onRecording={handleRecording} />
      )}

      {(phase === "uploading" || phase === "scoring") && (
        <div className="border-4 border-neo-black bg-white shadow-neo-md">
          <div className="bg-neo-black text-white px-4 py-2 font-black uppercase tracking-widest text-xs">
            {phase === "uploading" ? "Uploading Audio" : "Analysing Speech"}
          </div>
          {currentPrompt?.display_content && (
            <div className="border-b-4 border-neo-black bg-neo-secondary/40 p-4 text-center">
              <p className="font-black text-2xl opacity-50">{currentPrompt.display_content}</p>
            </div>
          )}
          <AnalysisSpinner label={phase === "uploading" ? "Uploading…" : "Analysing your speech…"} />
        </div>
      )}

      {phase === "scored" && score && (
        <div className="space-y-4">
          <ScoreDisplay score={score} />

          {/* Support pause */}
          {needsSupportPause && (
            <div className="border-4 border-neo-black bg-neo-muted shadow-neo-sm p-5 space-y-3">
              <p className="font-black uppercase text-sm tracking-widest">Take A Moment</p>
              <p className="font-medium text-sm">{getSupportMessage(score)}</p>
              <div className="grid grid-cols-2 gap-3">
                <NeoButton className="w-full" onClick={() => { if (canRetry) { retryExercise(); } else { void finishOrAdvance(); } }}>
                  {canRetry ? "Continue Task" : "Continue"}
                </NeoButton>
                <NeoButton variant="secondary" className="w-full" onClick={() => { toast.info("Take a short break. Come back when you feel ready."); router.push("/patient/tasks"); }}>
                  Take A Break
                </NeoButton>
              </div>
            </div>
          )}

          {/* No speech notice */}
          {noSpeech && canRetry && !needsSupportPause && (
            <div className="border-4 border-neo-black bg-neo-muted/30 px-4 py-3 text-sm font-medium">
              <strong>Speech not detected clearly.</strong> You can retry up to {MAX_ATTEMPTS} attempts.
            </div>
          )}

          {/* Terminal failure */}
          {terminalFailure && (
            <div className="border-4 border-neo-black bg-neo-secondary px-4 py-3 text-sm font-medium">
              <strong>All {MAX_ATTEMPTS} attempts used.</strong> The next exercise will use an adjusted level.
            </div>
          )}

          {/* Actions */}
          {!needsSupportPause && canRetry && (
            <NeoButton className="w-full" onClick={retryExercise}>Retry Exercise</NeoButton>
          )}
          {!needsSupportPause && !canRetry && (
            <NeoButton className="w-full" onClick={() => void finishOrAdvance()}>
              {score.pass_fail === "pass" ? "Next Exercise →" : "Continue →"}
            </NeoButton>
          )}
        </div>
      )}
    </div>
  );
}
