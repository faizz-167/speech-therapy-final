"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { createWebSocket, WebSocketHandle } from "@/lib/ws";
import { AttemptScore, Prompt, PollResult, RecordingMeta, SessionPhase } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { Recorder } from "@/components/patient/Recorder";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const NO_SPEECH_REASON = "No speech detected";
const UPLOAD_TIMEOUT_MS = 30_000;
const ANALYSIS_TIMEOUT_MS = 90_000;

export default function ExercisePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const router = useRouter();
  const userId = useAuthStore((s) => s.userId);

  const [sessionError, setSessionError] = useState("");
  const [promptIdx, setPromptIdx] = useState(0);
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

  const { data: prompts = [], isLoading: promptsLoading, error: promptsError } = useQuery<Prompt[]>({
    queryKey: ["exercise", "prompts", assignmentId],
    queryFn: () => api.get<Prompt[]>(`/patient/tasks/${assignmentId}/prompts`),
    retry: false,
  });

  const { data: sessionData, isLoading: sessionLoading, error: sessionLoadError } = useQuery<{ session_id: string }>({
    queryKey: ["exercise", "session", assignmentId],
    queryFn: () => api.post<{ session_id: string }>("/session/start", { assignment_id: assignmentId }),
    retry: false,
    staleTime: Infinity,
    gcTime: 0,
  });

  const sessionId = sessionData?.session_id ?? null;
  const isLoading = promptsLoading || sessionLoading;
  const loadError = promptsError ?? sessionLoadError;
  const currentPrompt = prompts[promptIdx];

  useEffect(() => {
    if (sessionLoadError instanceof Error) {
      setSessionError(sessionLoadError.message);
    } else if (promptsError instanceof Error) {
      setSessionError(promptsError.message);
    } else {
      setSessionError("");
    }
  }, [promptsError, sessionLoadError]);

  // WebSocket setup
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
          if (data.fail_reason === NO_SPEECH_REASON) {
            setNoSpeech(true);
            setPhase("scored");
          } else {
            setNoSpeech(false);
            setScore(data);
            setPhase("scored");
          }
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

  function continueAfterAnalysisTimeout() {
    clearAttemptTracking();
    setScore(null);
    setAttemptNumber(null);
    setNoSpeech(false);

    if (promptIdx < prompts.length - 1) {
      setPromptIdx((i) => i + 1);
      setPhase("instruction");
      return;
    }

    void api.post(`/patient/tasks/${assignmentId}/complete`, {}).then(() => {
      router.push("/patient/tasks");
    });
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
      const res = await api.upload<{ attempt_id: string; attempt_number: number }>(
        `/session/${sessionId}/attempt`,
        form,
        { timeout: UPLOAD_TIMEOUT_MS }
      );
      currentAttemptIdRef.current = res.attempt_id;
      setAttemptNumber(res.attempt_number);
      setPhase("scoring");

      pollIntervalRef.current = setInterval(async () => {
        try {
          const poll = await api.get<PollResult>(`/session/attempt/${res.attempt_id}`);
          if (poll.result && poll.result !== "pending") {
            clearAttemptTracking();
            if (poll.score?.fail_reason === NO_SPEECH_REASON) {
              setNoSpeech(true);
              setPhase("scored");
            } else if (poll.score) {
              setNoSpeech(false);
              setScore(poll.score);
              setPhase("scored");
            }
          }
        } catch {
          // Keep poll alive until timeout or WS wins
        }
      }, 2000);

      pollTimeoutRef.current = setTimeout(() => {
        clearAttemptTracking();
        setPhase((p) => (p === "scoring" ? "analysis_timeout" : p));
      }, ANALYSIS_TIMEOUT_MS);
    } catch (e: unknown) {
      clearAttemptTracking();
      if (e instanceof Error && e.name === "AbortError") {
        setUploadError("Upload timed out after 30 seconds. Please check your connection and try again.");
      } else {
        setUploadError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      }
      setPhase("error");
    }
  }

  function retryAfterNoSpeech() {
    clearAttemptTracking();
    setNoSpeech(false);
    setScore(null);
    setAttemptNumber(null);
    setPhase("instruction");
  }

  function retryAfterError() {
    clearAttemptTracking();
    setUploadError("");
    setNoSpeech(false);
    setScore(null);
    setAttemptNumber(null);
    setPhase("record");
  }

  function nextPrompt() {
    clearAttemptTracking();
    setNoSpeech(false);
    setScore(null);
    setAttemptNumber(null);
    if (promptIdx < prompts.length - 1) {
      setPromptIdx((i) => i + 1);
      setPhase("instruction");
    } else {
      api.post(`/patient/tasks/${assignmentId}/complete`, {}).then(() => {
        router.push("/patient/tasks");
      });
    }
  }

  if (isLoading) return <LoadingState label="Loading exercise..." />;

  if (phase === "analysis_timeout") {
    return (
      <NeoCard className="text-center py-8 space-y-4 max-w-2xl">
        <div className="text-5xl">⏱️</div>
        <p className="font-black text-xl uppercase">Analysis Is Taking Longer Than Expected</p>
        <p className="text-sm font-medium text-gray-600">
          Your attempt was saved — your therapist will be notified to review it.
        </p>
        <NeoButton
          className="w-full"
          onClick={() => {
            continueAfterAnalysisTimeout();
          }}
        >
          {promptIdx < prompts.length - 1 ? "Continue to Next Prompt" : "Complete Task"}
        </NeoButton>
      </NeoCard>
    );
  }

  if (phase === "error") {
    return (
      <ErrorState
        message={uploadError || sessionError || (loadError instanceof Error ? loadError.message : "Something went wrong")}
        onRetry={prompts.length > 0 ? retryAfterError : () => router.refresh()}
      />
    );
  }

  if (loadError) {
    return <ErrorState message={loadError instanceof Error ? loadError.message : "Failed to load"} onRetry={() => router.refresh()} />;
  }

  if (!currentPrompt) {
    return (
      <EmptyState
        icon="🎤"
        heading="No Prompts Available"
        subtext="This assignment does not have any prompts configured yet."
        cta={{ label: "Back to Tasks", onClick: () => router.push("/patient/tasks") }}
      />
    );
  }

  const isWarmup = currentPrompt.prompt_type === "warmup";

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
        </div>
        <div className="flex items-center gap-3">
          {wsReconnecting && (
            <span className="text-xs font-bold text-orange-600 border-2 border-orange-400 px-2 py-1 animate-pulse">
              Reconnecting…
            </span>
          )}
          {wsFallback && !wsReconnecting && (
            <span className="text-xs font-bold text-gray-500 border-2 border-gray-400 px-2 py-1">
              Polling mode
            </span>
          )}
          {attemptNumber ? (
            <span className="font-bold text-sm border-4 border-black px-3 py-1">
              Attempt {attemptNumber}
            </span>
          ) : null}
          <span className="font-bold text-sm border-4 border-black px-3 py-1">
            {promptIdx + 1} / {prompts.length}
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
            <p className="font-bold text-lg text-gray-500">{currentPrompt.instruction}</p>
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
              <p className="text-sm font-medium text-gray-500 mt-2">This may take 10–30 seconds</p>
            )}
          </div>
        </NeoCard>
      )}

      {phase === "scored" && noSpeech && (
        <NeoCard accent="accent" className="text-center py-8 space-y-4">
          <div className="text-5xl">🎙️</div>
          <p className="font-black text-xl uppercase">We Couldn&apos;t Hear You</p>
          <p className="text-sm font-medium text-gray-600">
            We couldn&apos;t detect speech in your recording. Please try again in a quieter environment and speak directly into your microphone.
          </p>
          <NeoButton onClick={retryAfterNoSpeech} className="w-full">
            Try Again
          </NeoButton>
        </NeoCard>
      )}

      {phase === "scored" && !noSpeech && score && (
        <>
          <ScoreDisplay score={score} />
          <NeoButton className="w-full" onClick={nextPrompt}>
            {promptIdx < prompts.length - 1 ? "Next Prompt →" : "Complete Task ✓"}
          </NeoButton>
        </>
      )}
    </div>
  );
}
