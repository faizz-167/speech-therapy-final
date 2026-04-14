"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { createWebSocket, WebSocketHandle } from "@/lib/ws";
import { AttemptScore, PollResult, RecordingMeta, SessionPhase, TaskExerciseState } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
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

export default function ExercisePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const router = useRouter();
  const userId = useAuthStore((state) => state.userId);

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

  const {
    data: exerciseState,
    isLoading,
    error,
    refetch,
  } = useQuery<TaskExerciseState>({
    queryKey: ["exercise", "state", assignmentId],
    queryFn: () => api.get<TaskExerciseState>(`/patient/tasks/${assignmentId}/session-state`),
    retry: false,
  });

  const currentPrompt = exerciseState?.current_prompt ?? null;
  const sessionId = exerciseState?.session_id ?? null;

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      wsRef.current = createWebSocket(
        userId,
        (data) => {
          if (!currentAttemptIdRef.current || data.attempt_id !== currentAttemptIdRef.current) return;
          clearAttemptTracking();
          setWsReconnecting(false);
          if (data.adaptive_decision === "escalated") {
            toast.error("This task has been escalated for therapist review.");
            router.push("/patient/tasks");
            return;
          }
          if (data.adaptive_decision === "alternate_prompt") {
            toast("Difficulty adjusted — trying a different exercise.");
            void finishOrAdvance();
            return;
          }
          setNoSpeech(data.fail_reason === NO_SPEECH_REASON);
          setScore(data);
          setPhase("scored");
        },
        (attempt) => {
          setWsReconnecting(true);
          toast.info(`Reconnecting to score delivery... (attempt ${attempt}/${5})`);
        },
        () => {
          setWsReconnecting(false);
          setWsFallback(true);
        }
      );
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      wsRef.current?.disconnect();
      wsRef.current = null;
      clearAttemptTracking();
    };
  }, [userId]);

  useEffect(() => {
    if (!exerciseState) return;
    if (exerciseState.escalated) {
      toast.error("This task has been escalated for therapist review.");
      router.push("/patient/tasks");
      return;
    }
    if (!exerciseState.current_prompt) {
      return;
    }
    setPhase("instruction");
    setScore(null);
    setAttemptNumber(null);
    setNoSpeech(false);
    setUploadError("");
  }, [exerciseState?.escalated, exerciseState?.current_prompt?.prompt_id, router]);

  useEffect(() => {
    if (!exerciseState || exerciseState.current_prompt || !exerciseState.task_complete || autoCompletingRef.current) {
      return;
    }
    autoCompletingRef.current = true;
    void api.post(`/patient/tasks/${assignmentId}/complete`, {}).finally(() => {
      router.push("/patient/tasks");
    });
  }, [assignmentId, exerciseState, router]);

  function clearAttemptTracking() {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    currentAttemptIdRef.current = null;
  }

  function playTTS() {
    if (!currentPrompt?.instruction) {
      setPhase("record");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(currentPrompt.instruction);
    utterance.onend = () => setPhase("record");
    speechSynthesis.speak(utterance);
  }

  async function finishOrAdvance() {
    clearAttemptTracking();
    setScore(null);
    setAttemptNumber(null);
    setNoSpeech(false);
    const nextState = await refetch();
    const state = nextState.data;
    if (state?.current_prompt) {
      setPhase("instruction");
      return;
    }
    try {
      const result = await api.post<{ message: string; status: string }>(`/patient/tasks/${assignmentId}/complete`, {});
      if (result.status === "pending") {
        toast.info(result.message);
      }
      router.push("/patient/tasks");
    } catch (completionError: unknown) {
      toast.error(completionError instanceof Error ? completionError.message : "Failed to finalize task.");
      router.push("/patient/tasks");
    }
  }

  function continueAfterAnalysisTimeout() {
    clearAttemptTracking();
    setScore(null);
    setAttemptNumber(null);
    setNoSpeech(false);
    toast.info("Your task remains pending until the exercise result is ready.");
    router.push("/patient/tasks");
  }

  async function handleRecording(blob: Blob, meta: RecordingMeta) {
    if (!sessionId || !currentPrompt) return;
    setPhase("uploading");
    setNoSpeech(false);
    setUploadError("");

    const form = new FormData();
    form.append("audio", blob, "recording.webm");
    form.append("prompt_id", currentPrompt.prompt_id);
    form.append("task_mode", currentPrompt.task_mode);
    form.append("prompt_type", currentPrompt.prompt_type);
    form.append("mic_activated_at", meta.micActivatedAt);
    if (meta.speechStartAt) {
      form.append("speech_start_at", meta.speechStartAt);
    }

    try {
      const response = await api.upload<{ attempt_id: string; attempt_number: number }>(
        `/session/${sessionId}/attempt`,
        form,
        { timeout: UPLOAD_TIMEOUT_MS }
      );
      currentAttemptIdRef.current = response.attempt_id;
      setAttemptNumber(response.attempt_number);
      setPhase("scoring");

      pollIntervalRef.current = setInterval(async () => {
        try {
          const poll = await api.get<PollResult>(`/session/attempt/${response.attempt_id}`);
          if (poll.result && poll.result !== "pending" && poll.score) {
            clearAttemptTracking();
            if (poll.score.adaptive_decision === "escalated") {
              toast.error("This task has been escalated for therapist review.");
              router.push("/patient/tasks");
              return;
            }
            if (poll.score.adaptive_decision === "alternate_prompt") {
              toast("Difficulty adjusted — trying a different exercise.");
              void finishOrAdvance();
              return;
            }
            setNoSpeech(poll.score.fail_reason === NO_SPEECH_REASON);
            setScore(poll.score);
            setPhase("scored");
          }
        } catch {
          // Keep polling until timeout or websocket success.
        }
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
    clearAttemptTracking();
    setUploadError("");
    setNoSpeech(false);
    setScore(null);
    setAttemptNumber(null);
    setPhase("instruction");
  }

  if (isLoading) {
    return <LoadingState label="Loading exercise..." />;
  }

  if (phase === "analysis_timeout") {
    return (
      <NeoCard className="text-center py-8 space-y-4 max-w-2xl">
        <div className="text-5xl">⏱️</div>
        <p className="font-black text-xl uppercase">Analysis Is Taking Longer Than Expected</p>
        <p className="text-sm font-medium text-neo-black/70">
          Your latest recording was saved. This task will stay pending until the result is reviewed.
        </p>
        <NeoButton className="w-full" onClick={continueAfterAnalysisTimeout}>
          Back to Tasks
        </NeoButton>
      </NeoCard>
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

  if (error) {
    return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} onRetry={() => router.refresh()} />;
  }

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
  const currentProgress = exerciseState.completed_prompts + 1;

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-black uppercase">Exercise</h1>
          {isWarmup && (
            <span className="bg-neo-secondary border-2 border-neo-black px-2 py-0.5 text-xs font-black uppercase">
              Warm-up
            </span>
          )}
          <span className="bg-white border-2 border-neo-black px-2 py-0.5 text-xs font-black uppercase">
            {exerciseState.current_level}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {wsReconnecting && (
            <span className="text-xs font-bold text-orange-600 border-2 border-orange-400 px-2 py-1 animate-pulse">
              Reconnecting…
            </span>
          )}
          {wsFallback && !wsReconnecting && (
            <span className="text-xs font-bold text-neo-black/70 border-2 border-gray-400 px-2 py-1">
              Polling mode
            </span>
          )}
          {attemptNumber ? (
            <span className="font-bold text-sm border-4 border-black px-3 py-1">
              Attempt {attemptNumber} / {MAX_ATTEMPTS}
            </span>
          ) : null}
          <span className="font-bold text-sm border-4 border-black px-3 py-1">
            {currentProgress} / {exerciseState.total_prompts}
          </span>
        </div>
      </div>

      {phase === "instruction" && (
        <NeoCard className="space-y-4">
          {currentPrompt.instruction && (
            <p className="font-bold text-lg">{currentPrompt.instruction}</p>
          )}
          {currentPrompt.display_content && (
            <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black">
              {currentPrompt.display_content}
            </div>
          )}
          <NeoButton onClick={playTTS} className="w-full">
            ▶ Play Instruction &amp; Start
          </NeoButton>
        </NeoCard>
      )}

      {phase === "record" && (
        <NeoCard className="space-y-4">
          {currentPrompt.instruction && (
            <p className="font-bold text-lg">{currentPrompt.instruction}</p>
          )}
          {currentPrompt.display_content && (
            <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black">
              {currentPrompt.display_content}
            </div>
          )}
          <Recorder onRecordingComplete={handleRecording} disabled={false} />
        </NeoCard>
      )}

      {(phase === "uploading" || phase === "scoring") && (
        <NeoCard className="space-y-4">
          {currentPrompt.instruction && (
            <p className="font-bold text-lg text-neo-black/70">{currentPrompt.instruction}</p>
          )}
          {currentPrompt.display_content && (
            <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black opacity-60">
              {currentPrompt.display_content}
            </div>
          )}
          <div className="text-center py-4">
            <p className="font-black text-lg animate-pulse">
              {phase === "uploading" ? "Uploading audio..." : "Analysing speech..."}
            </p>
            {phase === "scoring" && (
              <p className="text-sm font-medium text-neo-black/70 mt-2">This may take 10–30 seconds</p>
            )}
          </div>
        </NeoCard>
      )}

      {phase === "scored" && score && (
        <>
          <ScoreDisplay score={score} />
          {noSpeech && canRetry && (
            <NeoCard accent="accent" className="space-y-2">
              <p className="font-black uppercase text-sm">Retry Available</p>
              <p className="text-sm font-medium text-neo-black/80">
                Speech was not detected clearly enough. You can retry this exercise up to {MAX_ATTEMPTS} attempts.
              </p>
            </NeoCard>
          )}
          {terminalFailure && (
            <NeoCard accent="accent" className="space-y-2">
              <p className="font-black uppercase text-sm">Difficulty Adjusted</p>
              <p className="text-sm font-medium text-neo-black/80">
                This exercise used all {MAX_ATTEMPTS} attempts. The next exercise will use the adjusted level.
              </p>
            </NeoCard>
          )}
          {canRetry ? (
            <NeoButton className="w-full" onClick={retryExercise}>
              Retry Exercise
            </NeoButton>
          ) : (
            <NeoButton className="w-full" onClick={() => void finishOrAdvance()}>
              {score.pass_fail === "pass" ? "Next Exercise →" : "Continue →"}
            </NeoButton>
          )}
        </>
      )}
    </div>
  );
}
