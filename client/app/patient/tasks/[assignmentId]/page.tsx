"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { createWebSocket } from "@/lib/ws";
import { AttemptScore, Prompt, PollResult, RecordingMeta, SessionPhase } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { Recorder } from "@/components/patient/Recorder";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const NO_SPEECH_REASON = "No speech detected";

export default function ExercisePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const router = useRouter();
  const userId = useAuthStore((s) => s.userId);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [promptIdx, setPromptIdx] = useState(0);
  const [phase, setPhase] = useState<SessionPhase>("instruction");
  const [score, setScore] = useState<AttemptScore | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attemptNumber, setAttemptNumber] = useState<number | null>(null);
  const [noSpeech, setNoSpeech] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the current attempt_id so WS events from previous attempts are ignored
  const currentAttemptIdRef = useRef<string | null>(null);

  const currentPrompt = prompts[promptIdx];

  useEffect(() => {
    Promise.all([
      api.post<{ session_id: string }>("/session/start", { assignment_id: assignmentId }),
      api.get<Prompt[]>(`/patient/tasks/${assignmentId}/prompts`),
    ])
      .then(([session, p]) => {
        setSessionId(session.session_id);
        setPrompts(p);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [assignmentId]);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      wsRef.current = createWebSocket(userId, (data) => {
        // Only accept score events that match the currently active attempt
        if (!currentAttemptIdRef.current || data.attempt_id !== currentAttemptIdRef.current) return;
        if (pollIntervalRef.current !== null) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        if (pollTimeoutRef.current !== null) {
          clearTimeout(pollTimeoutRef.current);
          pollTimeoutRef.current = null;
        }
        if (data.fail_reason === NO_SPEECH_REASON) {
          setNoSpeech(true);
          setPhase("scored");
        } else {
          setNoSpeech(false);
          setScore(data);
          setPhase("scored");
        }
      });
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      wsRef.current?.close();
      wsRef.current = null;
      if (pollIntervalRef.current !== null) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      if (pollTimeoutRef.current !== null) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
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

  async function handleRecording(blob: Blob, meta: RecordingMeta) {
    if (!sessionId || !currentPrompt) return;
    setPhase("uploading");
    setNoSpeech(false);
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
        form
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
          // Keep the poll fallback alive until timeout or a WS event wins.
        }
      }, 2000);

      pollTimeoutRef.current = setTimeout(() => {
        clearAttemptTracking();
        setPhase((p) => (p === "scoring" ? "timeout" : p));
      }, 60000);
    } catch (e: unknown) {
      clearAttemptTracking();
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
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

  if (loading) return <LoadingState label="Loading exercise..." />;
  if (phase === "timeout") {
    return (
      <ErrorState
        message="Analysis timed out. Please try this prompt again."
        onRetry={() => {
          setError("");
          setNoSpeech(false);
          setScore(null);
          setAttemptNumber(null);
          setPhase("record");
        }}
      />
    );
  }
  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={
          prompts.length > 0
            ? () => {
                setError("");
                setNoSpeech(false);
                setScore(null);
                setAttemptNumber(null);
                setPhase("record");
              }
            : () => router.refresh()
        }
      />
    );
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
          <p className="font-black text-xl uppercase">No Speech Detected</p>
          <p className="text-sm font-medium text-gray-600">
            We couldn&apos;t hear you clearly. Make sure your microphone is working and speak
            directly into it when prompted.
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
