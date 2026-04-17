"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  BaselineItem, BaselineAssessment, AttemptResult, AttemptScore, BaselineResult,
} from "@/types";
import { ScoreDisplay } from "@/components/patient/ScoreDisplay";

type Phase = "loading" | "resume" | "ready" | "recording" | "uploading" | "polling" | "scored" | "complete" | "error";

interface ItemWithContext extends BaselineItem {
  sectionName: string; assessmentName: string;
  sectionItemIndex: number; sectionItemCount: number;
  globalSectionIndex: number; totalSections: number;
}
interface BaselineDraft { sessionId: string; itemIndex: number; }
const BASELINE_DRAFT_KEY = "patient-baseline-draft";

function readBaselineDraft(): BaselineDraft | null {
  try { const raw = window.localStorage.getItem(BASELINE_DRAFT_KEY); if (!raw) return null; return JSON.parse(raw) as BaselineDraft; } catch { return null; }
}
function writeBaselineDraft(d: BaselineDraft) { window.localStorage.setItem(BASELINE_DRAFT_KEY, JSON.stringify(d)); }
function clearBaselineDraft() { window.localStorage.removeItem(BASELINE_DRAFT_KEY); }

function buildItemList(assessments: BaselineAssessment[]): ItemWithContext[] {
  const result: ItemWithContext[] = [];
  let globalSectionIndex = 0;
  const totalSections = assessments.reduce((acc, a) => acc + a.sections.length, 0);
  for (const assessment of assessments) {
    for (const section of assessment.sections) {
      const sectionItemCount = section.items.length;
      section.items.forEach((item, sectionItemIndex) => {
        result.push({ ...item, sectionName: section.section_name, assessmentName: assessment.name, sectionItemIndex, sectionItemCount, globalSectionIndex, totalSections });
      });
      globalSectionIndex++;
    }
  }
  return result;
}

function toBaselineAttemptScore(ar: AttemptResult): AttemptScore {
  return {
    attempt_number: null, word_accuracy: ar.word_accuracy, phoneme_accuracy: ar.phoneme_accuracy,
    pa_available: ar.pa_available, fluency_score: ar.fluency_score, speech_rate_wpm: ar.speech_rate_wpm,
    speech_rate_score: ar.speech_rate_score, behavioral_score: null, emotion_score: ar.emotion_score ?? null,
    dominant_emotion: ar.dominant_emotion, engagement_score: ar.engagement_score, speech_score: null,
    confidence_score: ar.confidence_score, final_score: ar.computed_score, pass_fail: ar.pass_fail,
    adaptive_decision: null, asr_transcript: ar.asr_transcript, performance_level: null,
    review_recommended: false, fail_reason: null,
  };
}

function WaveformBars() {
  return (
    <div className="flex items-center justify-center gap-1.5 h-12" aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => (
        <div key={i} className={`w-3 bg-neo-accent border-2 border-neo-black animate-wave-${i + 1}`} style={{ height: "40px", transformOrigin: "center" }} />
      ))}
    </div>
  );
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
  const [elapsed, setElapsed] = useState(0);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const exercises = await api.get<BaselineAssessment[]>("/baseline/exercises");
        setAssessments(exercises);
        const items = buildItemList(exercises);
        setAllItems(items);
        const draft = readBaselineDraft();
        if (draft && draft.itemIndex < items.length) {
          setSessionId(draft.sessionId); setItemIndex(draft.itemIndex);
          setResumeDraft(draft); setPhase("resume"); return;
        }
        const { session_id } = await api.post<{ session_id: string }>("/baseline/start", {});
        setSessionId(session_id); writeBaselineDraft({ sessionId: session_id, itemIndex: 0 }); setPhase("ready");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load baseline exercises"); setPhase("error");
      }
    })();
  }, []);

  const currentItem = allItems[itemIndex] ?? null;

  const startFreshBaseline = async () => {
    try {
      clearBaselineDraft(); setResumeDraft(null); setAttemptResult(null); setCompletedScores([]);
      setItemIndex(0); setFinalResult(null); setError(null);
      const { session_id } = await api.post<{ session_id: string }>("/baseline/start", {});
      setSessionId(session_id); writeBaselineDraft({ sessionId: session_id, itemIndex: 0 }); setPhase("ready");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to start a new baseline session"); setPhase("error"); }
  };

  const startRecording = async () => {
    try {
      setElapsed(0);
      chunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.start();
      mediaRef.current = mr;
      setPhase("recording");
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } catch { setError("Microphone access denied."); setPhase("error"); }
  };

  const stopAndUpload = async () => {
    if (!mediaRef.current || !sessionId || !currentItem) return;
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
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
      const { attempt_id } = await api.upload<{ attempt_id: string }>(`/baseline/${sessionId}/attempt`, form, { timeout: 30_000 });
      setPhase("polling");
      await pollResult(attempt_id);
    } catch (e: unknown) {
      const msg = e instanceof Error && e.name === "AbortError" ? "Upload timed out." : (e instanceof Error ? e.message : "Upload failed");
      toast.error(msg); setError(msg); setPhase("error");
    }
  };

  const pollResult = async (attemptId: string) => {
    for (let i = 0; i < 45; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const res = await api.get<AttemptResult>(`/baseline/attempt/${attemptId}`);
        if (res.result === "scored" || res.result === "failed") { setAttemptResult(res); setPhase("scored"); return; }
      } catch { /* keep polling */ }
    }
    const msg = "Analysis is taking longer than expected. Your attempt was saved.";
    toast.info(msg); setError(msg); setPhase("error");
  };

  const nextItem = () => {
    const next = attemptResult ? [...completedScores, attemptResult] : completedScores;
    setCompletedScores(next); setAttemptResult(null);
    if (itemIndex + 1 >= allItems.length) { completeSession(); }
    else {
      const nextIdx = itemIndex + 1;
      setItemIndex(nextIdx);
      if (sessionId) writeBaselineDraft({ sessionId, itemIndex: nextIdx });
      setPhase("ready"); setElapsed(0);
    }
  };

  const completeSession = async () => {
    if (!sessionId) return;
    setPhase("uploading");
    try {
      const result = await api.post<BaselineResult>(`/baseline/${sessionId}/complete`, {});
      setFinalResult(result); clearBaselineDraft(); setPhase("complete");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to complete session"); setPhase("error"); }
  };

  function formatTime(s: number) {
    return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
  }

  if (phase === "loading") return <LoadingState label="Loading baseline exercises..." />;
  if (phase === "error") return <ErrorState message={error ?? "An error occurred"} onRetry={() => router.refresh()} />;

  if (phase === "resume" && resumeDraft) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center p-6">
        <div className="border-4 border-neo-black bg-white shadow-neo-lg max-w-md w-full">
          <div className="bg-neo-secondary border-b-4 border-neo-black px-6 py-4">
            <div className="inline-block bg-neo-black text-white px-3 py-0.5 font-black uppercase tracking-widest text-xs -rotate-1 mb-2">In Progress</div>
            <h2 className="text-3xl font-black uppercase tracking-tighter leading-none">Resume Baseline?</h2>
          </div>
          <div className="p-6 space-y-4">
            <p className="font-medium">You have a baseline session in progress. Resume from item {resumeDraft.itemIndex + 1} of {allItems.length}, or start over.</p>
            <div className="grid grid-cols-2 gap-3">
              <NeoButton className="w-full" onClick={() => { setResumeDraft(null); setPhase("ready"); }}>Resume</NeoButton>
              <NeoButton variant="ghost" className="w-full" onClick={() => void startFreshBaseline()}>Start Fresh</NeoButton>
            </div>
          </div>
        </div>
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

    const levelAccent: Record<string, string> = {
      easy: "bg-neo-secondary", beginner: "bg-neo-secondary", elementary: "bg-neo-secondary",
      medium: "bg-neo-muted", intermediate: "bg-neo-muted",
      hard: "bg-neo-accent", advanced: "bg-neo-accent", expert: "bg-neo-accent",
    };
    const levelBg = levelAccent[(displayLevel ?? "").toLowerCase()] ?? "bg-neo-secondary";

    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="border-4 border-neo-black bg-white shadow-neo-xl max-w-md w-full animate-pop-in">
          {/* Celebration header */}
          <div className={`border-b-4 border-neo-black ${levelBg} px-6 py-6 text-center`}>
            <div className="text-5xl mb-3">🎉</div>
            <div className="inline-block bg-neo-black text-white px-3 py-0.5 font-black uppercase tracking-widest text-xs -rotate-1 mb-2">Complete</div>
            <h2 className="text-4xl font-black uppercase tracking-tighter leading-none">Baseline Done!</h2>
          </div>

          {/* Score */}
          <div className="p-6 space-y-4">
            <div className="text-center border-4 border-neo-black bg-neo-bg p-6">
              <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-2">Your Score</p>
              <div className="text-8xl font-black leading-none animate-score-slam">{displayScore}</div>
              <div className="text-xl opacity-50 font-black">/100</div>
            </div>

            <div className="border-4 border-neo-black divide-y-4 divide-neo-black">
              {[
                { label: "Assessment", value: baselineName },
                { label: "Items Completed", value: allItems.length },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between items-center px-4 py-3">
                  <span className="font-black uppercase text-xs tracking-widest text-neo-black/50">{label}</span>
                  <span className="font-black">{value}</span>
                </div>
              ))}
              {displayLevel && (
                <div className={`flex justify-between items-center px-4 py-3 ${levelBg}`}>
                  <span className="font-black uppercase text-xs tracking-widest">Starting Level</span>
                  <span className="font-black text-xl capitalize border-4 border-neo-black bg-white px-3 py-1 shadow-neo-sm">{displayLevel}</span>
                </div>
              )}
            </div>

            <p className="text-sm font-medium text-center text-neo-black/60 border-4 border-neo-black/10 px-4 py-3 bg-neo-bg">
              Your therapist has been notified. They will review your results and create your therapy plan.
            </p>

            <NeoButton className="w-full" size="lg" onClick={() => router.push("/patient/home")}>
              Go to Home →
            </NeoButton>
          </div>
        </div>
      </div>
    );
  }

  const prevItem = itemIndex > 0 ? allItems[itemIndex - 1] : null;
  const isNewSection = itemIndex === 0 || (prevItem && prevItem.globalSectionIndex !== currentItem?.globalSectionIndex);
  const overallPct = Math.round(((itemIndex + 1) / allItems.length) * 100);

  return (
    <div className="animate-fade-up p-4 md:p-6 max-w-2xl mx-auto space-y-6">

      {/* ── HEADER + PROGRESS ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-xs -rotate-1">Baseline Assessment</div>
          <div className="border-4 border-neo-black bg-white px-3 py-1.5 font-black text-base shadow-neo-sm">
            {itemIndex + 1}<span className="text-neo-black/40 text-sm">/{allItems.length}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-5 border-4 border-neo-black bg-neo-bg overflow-hidden relative">
          <div
            className="h-full bg-neo-accent transition-all duration-500 flex items-center justify-end pr-2"
            style={{ width: `${overallPct}%` }}
          >
            {overallPct > 10 && <span className="font-black text-[10px] text-white">{overallPct}%</span>}
          </div>
        </div>

        {/* Section info */}
        {currentItem && (
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-neo-black/50">
            <span>Section {currentItem.globalSectionIndex + 1}/{currentItem.totalSections}</span>
            <span>·</span>
            <span>{currentItem.sectionName}</span>
            <span>·</span>
            <span>Item {currentItem.sectionItemIndex + 1}/{currentItem.sectionItemCount}</span>
          </div>
        )}
      </div>

      {/* ── SECTION TRANSITION ── */}
      {isNewSection && currentItem && (
        <div className="border-l-8 border-neo-black pl-4 py-1 animate-slide-right">
          <h2 className="text-2xl font-black uppercase tracking-tighter">{currentItem.sectionName}</h2>
          <p className="text-sm font-medium text-neo-black/60">{currentItem.sectionItemCount} item{currentItem.sectionItemCount !== 1 ? "s" : ""} in this section</p>
        </div>
      )}

      {/* ── ITEM CARD ── */}
      {currentItem && (
        <div className="border-4 border-neo-black bg-white shadow-neo-md overflow-hidden">
          {/* Item header */}
          <div className="bg-neo-black text-white px-5 py-3">
            <h3 className="font-black uppercase text-sm">{currentItem.task_name ?? "Exercise"}</h3>
          </div>

          <div className="p-6 space-y-4">
            {/* Instruction */}
            {currentItem.instruction && (
              <div className="border-4 border-neo-black bg-neo-bg px-4 py-3">
                <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">Instructions</p>
                <p className="font-bold">{currentItem.instruction}</p>
              </div>
            )}

            {/* Display content */}
            {currentItem.display_content && (
              <div className="border-8 border-neo-black bg-neo-secondary shadow-neo-sm p-5 text-center">
                <p className="text-3xl font-black tracking-tight">{currentItem.display_content}</p>
              </div>
            )}

            {/* Expected output */}
            {currentItem.expected_output && (
              <p className="text-xs font-medium text-neo-black/50 border-l-4 border-neo-black pl-2 italic">
                Expected: &ldquo;{currentItem.expected_output}&rdquo;
              </p>
            )}

            {/* ── PHASE-BASED UI ── */}
            {phase === "ready" && (
              <NeoButton onClick={startRecording} className="w-full" size="lg">
                🎤 Start Recording
              </NeoButton>
            )}

            {phase === "recording" && (
              <div className="space-y-3 animate-fade-up">
                <div className="border-4 border-neo-black bg-neo-accent flex items-center justify-between px-4 py-2">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 bg-neo-black rounded-full animate-pulse inline-block"></span>
                    <span className="font-black uppercase text-xs tracking-widest" role="status" aria-live="polite">Recording</span>
                  </div>
                  <span className="font-black text-lg tabular-nums">{formatTime(elapsed)}</span>
                </div>
                <WaveformBars />
                <NeoButton onClick={stopAndUpload} variant="ghost" className="w-full">
                  ■ Stop &amp; Submit
                </NeoButton>
              </div>
            )}

            {(phase === "uploading" || phase === "polling") && (
              <div className="py-6 text-center space-y-4">
                <WaveformBars />
                <p className="font-black uppercase tracking-widest">
                  {phase === "uploading" ? "Uploading…" : "Analysing your speech…"}
                </p>
              </div>
            )}

            {phase === "scored" && attemptResult && (
              <div className="space-y-4 animate-fade-up">
                <ScoreDisplay score={toBaselineAttemptScore(attemptResult)} />
                <NeoButton onClick={nextItem} className="w-full" size="lg">
                  {itemIndex + 1 >= allItems.length ? "Finish Assessment →" : "Next Item →"}
                </NeoButton>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
