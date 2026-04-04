"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { createWebSocket } from "@/lib/ws";
import { Prompt } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { Recorder } from "@/components/patient/Recorder";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

type Phase = "instruction" | "record" | "uploading" | "scoring" | "scored";

interface PollResult {
  result: string;
  score: Record<string, unknown> | null;
}

export default function ExercisePage() {
  const { assignmentId } = useParams<{ assignmentId: string }>();
  const userId = useAuthStore((s) => s.userId);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [promptIdx, setPromptIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("instruction");
  const [score, setScore] = useState<Record<string, unknown> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  const currentPrompt = prompts[promptIdx];

  useEffect(() => {
    Promise.all([
      api.post<{ session_id: string }>("/session/start", {}),
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
    wsRef.current = createWebSocket(userId, (data) => {
      setScore(data);
      setPhase("scored");
    });
    return () => {
      wsRef.current?.close();
    };
  }, [userId]);

  function playTTS() {
    if (!currentPrompt?.instruction) {
      setPhase("record");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(currentPrompt.instruction);
    utterance.onend = () => setPhase("record");
    speechSynthesis.speak(utterance);
  }

  async function handleRecording(blob: Blob) {
    if (!sessionId || !currentPrompt) return;
    setPhase("uploading");
    const form = new FormData();
    form.append("audio", blob, "recording.webm");
    form.append("prompt_id", currentPrompt.prompt_id);
    form.append("task_mode", currentPrompt.task_mode);
    form.append("prompt_type", currentPrompt.prompt_type);
    try {
      const res = await api.upload<{ attempt_id: string }>(
        `/session/${sessionId}/attempt`,
        form
      );
      setPhase("scoring");
      const pollInterval = setInterval(async () => {
        const poll = await api.get<PollResult>(`/session/attempt/${res.attempt_id}`);
        if (poll.result && poll.result !== "pending" && poll.score) {
          setScore(poll.score);
          setPhase("scored");
          clearInterval(pollInterval);
        }
      }, 3000);
      setTimeout(() => clearInterval(pollInterval), 30000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setPhase("record");
    }
  }

  function nextPrompt() {
    if (promptIdx < prompts.length - 1) {
      setPromptIdx((i) => i + 1);
      setPhase("instruction");
      setScore(null);
    } else {
      api.post(`/patient/tasks/${assignmentId}/complete`, {}).then(() => {
        window.location.href = "/patient/tasks";
      });
    }
  }

  if (loading) return <SkeletonList />;
  if (error) return <ErrorBanner message={error} />;
  if (!currentPrompt) return <ErrorBanner message="No prompts available for this task." />;

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black uppercase">Exercise</h1>
        <span className="font-bold text-sm border-4 border-black px-3 py-1">
          {promptIdx + 1} / {prompts.length}
        </span>
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
          {currentPrompt.display_content && (
            <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black">
              {currentPrompt.display_content}
            </div>
          )}
          <Recorder onRecordingComplete={handleRecording} disabled={false} />
        </NeoCard>
      )}

      {phase === "uploading" && (
        <NeoCard className="text-center py-8">
          <p className="font-black text-lg animate-pulse">Uploading audio...</p>
        </NeoCard>
      )}

      {phase === "scoring" && (
        <NeoCard className="text-center py-8">
          <p className="font-black text-lg animate-pulse">Analysing speech...</p>
          <p className="text-sm font-medium text-gray-500 mt-2">This may take 10–30 seconds</p>
        </NeoCard>
      )}

      {phase === "scored" && score && (
        <>
          <ScoreDisplay score={score as Parameters<typeof ScoreDisplay>[0]["score"]} />
          <NeoButton className="w-full" onClick={nextPrompt}>
            {promptIdx < prompts.length - 1 ? "Next Prompt →" : "Complete Task ✓"}
          </NeoButton>
        </>
      )}
    </div>
  );
}
