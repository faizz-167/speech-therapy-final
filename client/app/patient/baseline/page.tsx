"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  BaselineItem,
  BaselineAssessment,
  AttemptResult,
  BaselineResult,
} from "@/types";

type Phase = "loading" | "ready" | "recording" | "uploading" | "polling" | "scored" | "complete" | "error";

export default function BaselinePage() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<BaselineAssessment[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [allItems, setAllItems] = useState<BaselineItem[]>([]);
  const [itemIndex, setItemIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);
  const [completedScores, setCompletedScores] = useState<AttemptResult[]>([]);
  const [finalResult, setFinalResult] = useState<BaselineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Load exercises and start baseline session
  useEffect(() => {
    (async () => {
      try {
        const exercises = await api.get<BaselineAssessment[]>("/baseline/exercises");
        setAssessments(exercises);
        const flat: BaselineItem[] = exercises.flatMap((a) =>
          a.sections.flatMap((s) => s.items)
        );
        setAllItems(flat);

        const { session_id } = await api.post<{ session_id: string }>("/baseline/start", {});
        setSessionId(session_id);
        setPhase("ready");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load baseline exercises");
        setPhase("error");
      }
    })();
  }, []);

  const currentItem = allItems[itemIndex] ?? null;

  const startRecording = async () => {
    try {
      chunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.start();
      mediaRef.current = mr;
      setPhase("recording");
    } catch {
      setError("Microphone access denied.");
      setPhase("error");
    }
  };

  const stopAndUpload = async () => {
    if (!mediaRef.current || !sessionId || !currentItem) return;
    setPhase("uploading");

    await new Promise<void>((resolve) => {
      mediaRef.current!.onstop = () => resolve();
      mediaRef.current!.stop();
      mediaRef.current!.stream.getTracks().forEach((t) => t.stop());
    });

    try {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("audio", blob, "attempt.webm");
      form.append("item_id", currentItem.item_id);

      const { attempt_id } = await api.upload<{ attempt_id: string }>(
        `/baseline/${sessionId}/attempt`,
        form
      );
      setPhase("polling");
      await pollResult(attempt_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setPhase("error");
    }
  };

  const pollResult = async (attemptId: string) => {
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const res = await api.get<AttemptResult>(`/baseline/attempt/${attemptId}`);
        if (res.result === "scored" || res.result === "failed") {
          setAttemptResult(res);
          setPhase("scored");
          return;
        }
      } catch {
        // keep polling
      }
    }
    setError("Scoring timed out. Please try again.");
    setPhase("error");
  };

  const nextItem = () => {
    if (attemptResult) {
      setCompletedScores((prev) => [...prev, attemptResult]);
    }
    setAttemptResult(null);
    if (itemIndex + 1 >= allItems.length) {
      completeSession();
    } else {
      setItemIndex((i) => i + 1);
      setPhase("ready");
    }
  };

  const completeSession = async () => {
    if (!sessionId) return;
    setPhase("uploading");
    try {
      const result = await api.post<BaselineResult>(`/baseline/${sessionId}/complete`, {});
      setFinalResult(result);
      setPhase("complete");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to complete session");
      setPhase("error");
    }
  };

  if (phase === "loading") {
    return <LoadingState message="Loading baseline exercises…" />;
  }

  if (phase === "error") {
    return <ErrorState message={error ?? "An error occurred"} onRetry={() => router.refresh()} />;
  }

  if (phase === "complete") {
    const avg = completedScores.length
      ? Math.round(completedScores.reduce((s, a) => s + (a.computed_score ?? 0), 0) / completedScores.length)
      : 0;
    const displayScore = finalResult?.raw_score ?? avg;
    const displayLevel = finalResult?.level ?? null;
    return (
      <div className="min-h-screen flex items-center justify-center">
        <NeoCard className="p-8 max-w-md w-full text-center">
          <h2 className="text-2xl font-bold mb-2">Baseline Complete!</h2>
          <p className="text-gray-600 mb-2">Average score: <strong>{displayScore}</strong></p>
          {displayLevel && (
            <p className="text-gray-600 mb-4">
              Starting level: <strong className="capitalize">{displayLevel}</strong>
            </p>
          )}
          <NeoButton onClick={() => router.push("/patient/home")}>
            Go to Home
          </NeoButton>
        </NeoCard>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6">
      <h1 className="text-2xl font-bold mb-6">Baseline Assessment</h1>
      <p className="text-sm text-gray-500 mb-6">
        Item {itemIndex + 1} of {allItems.length}
      </p>

      {currentItem && (
        <NeoCard className="p-6 max-w-2xl mx-auto">
          <h2 className="text-xl font-semibold mb-2">{currentItem.task_name ?? "Exercise"}</h2>
          {currentItem.instruction && (
            <p className="text-gray-600 mb-3">{currentItem.instruction}</p>
          )}
          {currentItem.display_content && (
            <div className="bg-gray-50 rounded-lg p-4 mb-4 text-center text-lg font-medium">
              {currentItem.display_content}
            </div>
          )}

          {phase === "ready" && (
            <NeoButton onClick={startRecording} className="w-full">
              Start Recording
            </NeoButton>
          )}

          {phase === "recording" && (
            <div className="text-center">
              <div className="w-4 h-4 bg-red-500 rounded-full animate-pulse mx-auto mb-3" />
              <p className="text-sm text-gray-600 mb-4">Recording… speak now</p>
              <NeoButton onClick={stopAndUpload} className="w-full">
                Stop &amp; Submit
              </NeoButton>
            </div>
          )}

          {(phase === "uploading" || phase === "polling") && (
            <div className="text-center py-6">
              <p className="text-gray-600">
                {phase === "uploading" ? "Uploading…" : "Analyzing your speech…"}
              </p>
            </div>
          )}

          {phase === "scored" && attemptResult && (
            <div className="text-center">
              <p className="text-lg font-semibold mb-1">
                Score: {attemptResult.computed_score != null ? Math.round(attemptResult.computed_score) : "—"}
              </p>
              {attemptResult.asr_transcript && (
                <p className="text-sm text-gray-500 mb-4">
                  Heard: &ldquo;{attemptResult.asr_transcript}&rdquo;
                </p>
              )}
              <NeoButton onClick={nextItem} className="w-full">
                {itemIndex + 1 >= allItems.length ? "Finish" : "Next Item"}
              </NeoButton>
            </div>
          )}
        </NeoCard>
      )}
    </div>
  );
}
