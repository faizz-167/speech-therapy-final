"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  BaselineItem,
  BaselineAssessment,
  AttemptResult,
  AttemptScore,
  BaselineResult,
} from "@/types";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";

type Phase =
  | "loading"
  | "resume"
  | "ready"
  | "recording"
  | "uploading"
  | "polling"
  | "scored"
  | "complete"
  | "error";

interface ItemWithContext extends BaselineItem {
  sectionName: string;
  assessmentName: string;
  sectionItemIndex: number;
  sectionItemCount: number;
  globalSectionIndex: number;
  totalSections: number;
}

interface BaselineDraft {
  sessionId: string;
  itemIndex: number;
}

const BASELINE_DRAFT_KEY = "patient-baseline-draft";

function readBaselineDraft(): BaselineDraft | null {
  try {
    const raw = window.localStorage.getItem(BASELINE_DRAFT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as BaselineDraft;
  } catch {
    return null;
  }
}

function writeBaselineDraft(draft: BaselineDraft) {
  window.localStorage.setItem(BASELINE_DRAFT_KEY, JSON.stringify(draft));
}

function clearBaselineDraft() {
  window.localStorage.removeItem(BASELINE_DRAFT_KEY);
}

function buildItemList(assessments: BaselineAssessment[]): ItemWithContext[] {
  const result: ItemWithContext[] = [];
  let globalSectionIndex = 0;
  const totalSections = assessments.reduce((acc, a) => acc + a.sections.length, 0);
  for (const assessment of assessments) {
    for (const section of assessment.sections) {
      const sectionItemCount = section.items.length;
      section.items.forEach((item, sectionItemIndex) => {
        result.push({
          ...item,
          sectionName: section.section_name,
          assessmentName: assessment.name,
          sectionItemIndex,
          sectionItemCount,
          globalSectionIndex,
          totalSections,
        });
      });
      globalSectionIndex++;
    }
  }
  return result;
}

function toBaselineAttemptScore(attemptResult: AttemptResult): AttemptScore {
  return {
    attempt_number: null,
    word_accuracy: attemptResult.word_accuracy,
    phoneme_accuracy: attemptResult.phoneme_accuracy,
    pa_available: attemptResult.pa_available,
    fluency_score: attemptResult.fluency_score,
    speech_rate_wpm: attemptResult.speech_rate_wpm,
    speech_rate_score: attemptResult.speech_rate_score,
    behavioral_score: null,
    emotion_score: null,
    dominant_emotion: attemptResult.dominant_emotion,
    engagement_score: attemptResult.engagement_score,
    speech_score: null,
    confidence_score: attemptResult.confidence_score,
    final_score: attemptResult.computed_score,
    pass_fail: attemptResult.pass_fail,
    adaptive_decision: null,
    asr_transcript: attemptResult.asr_transcript,
    performance_level: null,
    review_recommended: false,
    fail_reason: null,
  };
}

export default function BaselinePage() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<BaselineAssessment[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [allItems, setAllItems] = useState<ItemWithContext[]>([]);
  const [itemIndex, setItemIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);
  const [completedScores, setCompletedScores] = useState<AttemptResult[]>([]);
  const [finalResult, setFinalResult] = useState<BaselineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resumeDraft, setResumeDraft] = useState<BaselineDraft | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const exercises = await api.get<BaselineAssessment[]>("/baseline/exercises");
        setAssessments(exercises);
        const items = buildItemList(exercises);
        setAllItems(items);
        const draft = readBaselineDraft();
        if (draft && draft.itemIndex < items.length) {
          setSessionId(draft.sessionId);
          setItemIndex(draft.itemIndex);
          setResumeDraft(draft);
          setPhase("resume");
          return;
        }
        const { session_id } = await api.post<{ session_id: string }>("/baseline/start", {});
        setSessionId(session_id);
        writeBaselineDraft({ sessionId: session_id, itemIndex: 0 });
        setPhase("ready");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load baseline exercises");
        setPhase("error");
      }
    })();
  }, []);

  const currentItem = allItems[itemIndex] ?? null;

  const startFreshBaseline = async () => {
    try {
      clearBaselineDraft();
      setResumeDraft(null);
      setAttemptResult(null);
      setCompletedScores([]);
      setItemIndex(0);
      setFinalResult(null);
      setError(null);
      const { session_id } = await api.post<{ session_id: string }>("/baseline/start", {});
      setSessionId(session_id);
      writeBaselineDraft({ sessionId: session_id, itemIndex: 0 });
      setPhase("ready");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start a new baseline session");
      setPhase("error");
    }
  };

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
        form,
        { timeout: 30_000 }
      );
      setPhase("polling");
      await pollResult(attempt_id);
    } catch (e: unknown) {
      const msg = e instanceof Error && e.name === "AbortError"
        ? "Upload timed out. Please check your connection and try again."
        : (e instanceof Error ? e.message : "Upload failed");
      toast.error(msg);
      setError(msg);
      setPhase("error");
    }
  };

  const pollResult = async (attemptId: string) => {
    // 45 × 2s = 90s timeout
    for (let i = 0; i < 45; i++) {
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
    const msg = "Analysis is taking longer than expected. Your attempt was saved — your therapist will be notified.";
    toast.info(msg);
    setError(msg);
    setPhase("error");
  };

  const nextItem = () => {
    const nextCompletedScores = attemptResult ? [...completedScores, attemptResult] : completedScores;
    setCompletedScores(nextCompletedScores);
    setAttemptResult(null);
    if (itemIndex + 1 >= allItems.length) {
      completeSession();
    } else {
      const nextIndex = itemIndex + 1;
      setItemIndex(nextIndex);
      if (sessionId) {
        writeBaselineDraft({ sessionId, itemIndex: nextIndex });
      }
      setPhase("ready");
    }
  };

  const completeSession = async () => {
    if (!sessionId) return;
    setPhase("uploading");
    try {
      const result = await api.post<BaselineResult>(`/baseline/${sessionId}/complete`, {});
      setFinalResult(result);
      clearBaselineDraft();
      setPhase("complete");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to complete session");
      setPhase("error");
    }
  };

  if (phase === "loading") {
    return <LoadingState label="Loading baseline exercises..." />;
  }

  if (phase === "error") {
    return <ErrorState message={error ?? "An error occurred"} onRetry={() => router.refresh()} />;
  }

  if (phase === "resume" && resumeDraft) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center p-6">
        <NeoCard className="max-w-xl space-y-5 p-8">
          <div className="inline-block bg-neo-warning border-4 border-neo-black px-3 py-1 font-black uppercase tracking-widest text-sm shadow-neo-sm">
            Resume Baseline
          </div>
          <h2 className="text-3xl font-black uppercase tracking-tighter">Continue where you left off?</h2>
          <p className="font-medium text-neo-black/80">
            Your previous baseline session is still in progress. You can resume from item {resumeDraft.itemIndex + 1} of {allItems.length}, or start over.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <NeoButton className="flex-1" onClick={() => {
              setResumeDraft(null);
              setPhase("ready");
            }}>
              Resume Baseline
            </NeoButton>
            <NeoButton variant="ghost" className="flex-1" onClick={() => void startFreshBaseline()}>
              Start Fresh
            </NeoButton>
          </div>
        </NeoCard>
      </div>
    );
  }

  if (phase === "complete") {
    const avg = completedScores.length
      ? Math.round(completedScores.reduce((s, a) => s + (a.computed_score ?? 0), 0) / completedScores.length)
      : 0;
    const displayScore = finalResult?.raw_score ?? avg;
    const displayLevel = finalResult?.level ?? null;
    const baselineName = finalResult?.baseline_name ?? assessments[0]?.name ?? "Baseline";
    const itemCount = allItems.length;

    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <NeoCard className="p-8 max-w-md w-full space-y-6">
          <div className="inline-block bg-neo-secondary border-4 border-neo-black px-3 py-1 font-black uppercase tracking-widest text-sm -rotate-1 shadow-neo-sm">
            Complete
          </div>
          <h2 className="text-4xl font-black uppercase tracking-tighter">Baseline Done!</h2>
          <div className="border-4 border-neo-black divide-y-4 divide-neo-black">
            <div className="flex justify-between items-center px-4 py-3">
              <span className="font-black uppercase text-sm text-neo-black/70">Assessment</span>
              <span className="font-black">{baselineName}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-3">
              <span className="font-black uppercase text-sm text-neo-black/70">Items Completed</span>
              <span className="font-black">{itemCount}</span>
            </div>
            <div className="flex justify-between items-center px-4 py-3">
              <span className="font-black uppercase text-sm text-neo-black/70">Raw Score</span>
              <span className="font-black text-2xl">{displayScore}</span>
            </div>
            {displayLevel && (
              <div className="flex justify-between items-center px-4 py-3 bg-neo-accent">
                <span className="font-black uppercase text-sm">Starting Level</span>
                <span className="font-black text-xl capitalize">{displayLevel}</span>
              </div>
            )}
          </div>
          <NeoButton className="w-full" onClick={() => router.push("/patient/home")}>
            Go to Home
          </NeoButton>
        </NeoCard>
      </div>
    );
  }

  // Section transition: detect when we're on the first item of a new section
  const prevItem = itemIndex > 0 ? allItems[itemIndex - 1] : null;
  const isNewSection =
    itemIndex === 0 ||
    (prevItem && prevItem.globalSectionIndex !== currentItem?.globalSectionIndex);

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl mx-auto p-4 md:p-6">
      <div>
        <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-sm mb-3 rotate-[-1deg]">
          Baseline Assessment
        </div>
        {/* Overall progress */}
        <div className="flex items-center justify-between border-4 border-neo-black px-4 py-2 bg-white shadow-neo-sm">
          <span className="font-black uppercase text-xs tracking-widest text-neo-black/70">Overall Progress</span>
          <span className="font-black text-lg">
            Item {itemIndex + 1} of {allItems.length}
          </span>
        </div>
        {/* Progress bar */}
        <div className="h-3 border-4 border-neo-black mt-2">
          <div
            className="h-full bg-neo-accent"
            style={{ width: `${Math.round(((itemIndex + 1) / allItems.length) * 100)}%` }}
          />
        </div>
      </div>

      {/* Section header shown on first item of each section */}
      {isNewSection && currentItem && (
        <div className="border-l-8 border-neo-black pl-4">
          <p className="text-xs font-black uppercase tracking-widest text-neo-black/70">
            Section {currentItem.globalSectionIndex + 1} of {currentItem.totalSections}
          </p>
          <h2 className="text-2xl font-black uppercase tracking-tight">{currentItem.sectionName}</h2>
          <p className="text-sm font-medium text-neo-black/70">
            {currentItem.sectionItemCount} item{currentItem.sectionItemCount !== 1 ? "s" : ""}
          </p>
        </div>
      )}

      {/* Section progress */}
      {currentItem && (
        <div className="text-xs font-black uppercase tracking-widest text-neo-black/70">
          Section {currentItem.globalSectionIndex + 1} — {currentItem.sectionName} &mdash;{" "}
          item {currentItem.sectionItemIndex + 1}/{currentItem.sectionItemCount}
        </div>
      )}

      {currentItem && (
        <NeoCard className="p-6 space-y-4">
          <h3 className="text-xl font-black uppercase">{currentItem.task_name ?? "Exercise"}</h3>
          {currentItem.instruction && (
            <p className="font-bold text-neo-black/80">{currentItem.instruction}</p>
          )}
          {currentItem.display_content && (
            <div className="border-4 border-neo-black bg-[#FFD93D] p-4 text-xl font-black text-center">
              {currentItem.display_content}
            </div>
          )}
          {currentItem.expected_output && (
            <p className="text-sm font-medium text-neo-black/70 italic">
              Expected: &ldquo;{currentItem.expected_output}&rdquo;
            </p>
          )}

          {phase === "ready" && (
            <NeoButton onClick={startRecording} className="w-full">
              🎤 Start Recording
            </NeoButton>
          )}

          {phase === "recording" && (
            <div className="text-center space-y-4">
              <div className="flex items-center justify-center gap-3">
                <div className="w-4 h-4 bg-red-500 border-2 border-neo-black rounded-full animate-pulse" />
                <span className="font-black uppercase tracking-widest">Recording…</span>
              </div>
              <NeoButton onClick={stopAndUpload} variant="ghost" className="w-full">
                Stop &amp; Submit
              </NeoButton>
            </div>
          )}

          {(phase === "uploading" || phase === "polling") && (
            <div className="text-center py-4">
              <p className="font-black uppercase tracking-widest animate-pulse">
                {phase === "uploading" ? "Uploading…" : "Analysing your speech…"}
              </p>
            </div>
          )}

          {phase === "scored" && attemptResult && (
            <div className="space-y-4">
              <ScoreDisplay score={toBaselineAttemptScore(attemptResult)} />
              <NeoButton onClick={nextItem} className="w-full">
                {itemIndex + 1 >= allItems.length ? "Finish Assessment" : "Next Item →"}
              </NeoButton>
            </div>
          )}
        </NeoCard>
      )}
    </div>
  );
}
