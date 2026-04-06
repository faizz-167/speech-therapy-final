"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

interface BaselineItem {
  item_id: string;
  task_name: string | null;
  instruction: string | null;
  display_content: string | null;
  expected_output: string | null;
  response_type: string | null;
}
interface BaselineSection { section_id: string; section_name: string; instructions: string | null; items: BaselineItem[]; }
interface BaselineAssessment { baseline_id: string; name: string; domain: string; sections: BaselineSection[]; }

type ItemPhase = "prompt" | "recording" | "recorded" | "rated";

// Emoji map for common speech therapy picture naming items
const EMOJI_MAP: Record<string, string> = {
  apple: "🍎", ball: "⚽", cat: "🐱", dog: "🐶", house: "🏠",
  tree: "🌳", car: "🚗", fish: "🐟", bird: "🐦", flower: "🌸",
  book: "📚", cup: "☕", key: "🔑", sun: "☀️", moon: "🌙",
  star: "⭐", heart: "❤️", hand: "✋", eye: "👁️", nose: "👃",
  shoe: "👟", hat: "🎩", chair: "🪑", bed: "🛏️", door: "🚪",
  pen: "✏️", milk: "🥛", egg: "🥚", bread: "🍞", cake: "🎂",
  water: "💧", fire: "🔥", cloud: "☁️", rain: "🌧️", snow: "❄️",
  baby: "👶", boy: "👦", girl: "👧", man: "👨", woman: "👩",
  horse: "🐎", cow: "🐄", pig: "🐷", duck: "🦆", frog: "🐸",
  elephant: "🐘", lion: "🦁", bear: "🐻", rabbit: "🐰",
  bus: "🚌", train: "🚂", plane: "✈️", boat: "⛵", bike: "🚲",
  phone: "📱", lamp: "💡", clock: "⏰", bowl: "🥣", fork: "🍴",
  spoon: "🥄", bag: "👜", kite: "🪁", leaf: "🍃", ring: "💍",
  drum: "🥁", flag: "🚩", rope: "🪢", sock: "🧦", coat: "🧥",
  banana: "🍌", orange: "🍊", grape: "🍇", lemon: "🍋", pear: "🍐",
  tomato: "🍅", corn: "🌽", carrot: "🥕", potato: "🥔", cake2: "🧁",
};

function getPictureEmoji(word: string | null): string {
  if (!word) return "🖼️";
  const key = word.trim().toLowerCase().split(" ")[0];
  return EMOJI_MAP[key] ?? "🖼️";
}

function isPictureNaming(item: BaselineItem): boolean {
  if (item.response_type?.toLowerCase().includes("picture")) return true;
  if (item.task_name?.toLowerCase().includes("picture")) return true;
  if (item.task_name?.toLowerCase().includes("naming")) return true;
  return false;
}

export default function BaselinePage() {
  const [assessments, setAssessments] = useState<BaselineAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentItemIdx, setCurrentItemIdx] = useState(0);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<{ raw_score: number; level: string } | null>(null);

  // Per-item recording state
  const [phase, setPhase] = useState<ItemPhase>("prompt");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const allItems = assessments.flatMap(a =>
    a.sections.flatMap(s => s.items.map(i => ({ ...i, baseline_id: a.baseline_id, assessment_name: a.name })))
  );
  const currentItem = allItems[currentItemIdx];
  const isLast = currentItemIdx === allItems.length - 1;

  useEffect(() => {
    api.get<BaselineAssessment[]>("/baseline/exercises")
      .then(setAssessments)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  // Reset recording state when moving to a new item
  useEffect(() => {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    setBlobUrl(null);
    setPhase("prompt");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentItemIdx]);

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        setPhase("recorded");
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRef.current = mr;
      setPhase("recording");
    } catch {
      setError("Microphone access denied. Please allow microphone and reload.");
    }
  }

  function stopRecording() {
    mediaRef.current?.stop();
  }

  function handleRetry() {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    setBlobUrl(null);
    setPhase("prompt");
  }

  function handleScore(score: number) {
    if (!currentItem) return;
    setScores(prev => ({ ...prev, [currentItem.item_id]: score }));
    setPhase("rated");
  }

  function handleNext() {
    if (!isLast) {
      setCurrentItemIdx(i => i + 1);
    }
  }

  async function handleSubmit() {
    const firstAssessment = assessments[0];
    if (!firstAssessment) return;
    try {
      const item_scores = Object.entries(scores).map(([item_id, score]) => ({ item_id, score }));
      const res = await api.post<{ raw_score: number; level: string }>("/baseline/submit", {
        baseline_id: firstAssessment.baseline_id,
        item_scores,
      });
      setResult(res);
      setSubmitted(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submit failed");
    }
  }

  if (loading) return <SkeletonList />;
  if (error) return <ErrorBanner message={error} />;
  if (submitted && result) return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center space-y-8 animate-pop-in">
      <h1 className="text-4xl font-black uppercase tracking-widest px-4 text-center">BASELINE ASSESSMENT</h1>
      
      <div className="bg-neo-warning border-4 sm:border-8 border-neo-black p-8 sm:p-12 max-w-3xl w-full text-center shadow-neo-lg relative">
        <div className="text-6xl mb-6">🎉</div>
        <h2 className="text-3xl sm:text-4xl font-black uppercase tracking-tight mb-8">GREAT WORK!</h2>
        
        <p className="font-bold text-lg sm:text-xl mb-4 leading-relaxed">
           You&apos;ve completed your baseline assessment — that took real effort and courage.
        </p>
        <p className="font-bold text-lg sm:text-xl mb-12 leading-relaxed">
           Your therapist will review your results and craft a personalised therapy plan just for you. You&apos;ll be notified once it&apos;s ready to begin.
        </p>
        
        <div className="inline-block relative hover:scale-105 transition-transform duration-100 ease-linear">
           <a href="/patient/home">
             <NeoButton size="lg" className="px-12 py-6 text-xl tracking-widest border-4 bg-neo-accent hover:bg-neo-accent border-neo-black shadow-neo-md text-neo-black hover:text-white transition-colors">
               BACK TO HOME
             </NeoButton>
           </a>
        </div>
      </div>
    </div>
  );

  if (!currentItem) return <ErrorBanner message="No baseline exercises found for your assigned defects." />;

  const pictureTask = isPictureNaming(currentItem);
  const scored = scores[currentItem.item_id] !== undefined;
  const canSubmit = isLast && scored;

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black uppercase">Baseline Assessment</h1>
        <span className="font-bold text-sm border-4 border-black px-3 py-1">
          {currentItemIdx + 1} / {allItems.length}
        </span>
      </div>
      <div className="w-full bg-gray-200 border-2 border-black h-3">
        <div className="bg-[#FF6B6B] h-full transition-all" style={{ width: `${(currentItemIdx / allItems.length) * 100}%` }} />
      </div>

      {/* Prompt card */}
      <NeoCard className="space-y-4">
        {currentItem.task_name && (
          <p className="font-black uppercase text-sm text-gray-500">{currentItem.task_name}</p>
        )}
        {currentItem.instruction && (
          <p className="font-bold">{currentItem.instruction}</p>
        )}
        {pictureTask && currentItem.display_content ? (
          <div className="border-4 border-black bg-[#FFD93D] p-8 text-center rounded">
            <div className="text-9xl leading-none select-none" role="img" aria-label="picture to name">
              {getPictureEmoji(currentItem.display_content)}
            </div>
            <p className="sr-only">{currentItem.display_content}</p>
          </div>
        ) : currentItem.display_content ? (
          <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black">
            {currentItem.display_content}
          </div>
        ) : null}
      </NeoCard>

      {/* Recording card */}
      <NeoCard accent="muted" className="space-y-4">
        <p className="font-black uppercase text-sm">Record your response:</p>

        {phase === "prompt" && (
          <NeoButton onClick={startRecording} className="w-full">
            🎙 Start Recording
          </NeoButton>
        )}

        {phase === "recording" && (
          <div className="space-y-3 text-center">
            <div className="text-[#FF6B6B] font-black animate-pulse text-lg">● RECORDING — speak now</div>
            <NeoButton variant="ghost" onClick={stopRecording} className="w-full">
              ■ Stop Recording
            </NeoButton>
          </div>
        )}

        {(phase === "recorded" || phase === "rated") && (
          <div className="space-y-3">
            <p className="text-sm font-bold text-green-700">Recording complete ✓</p>
            {blobUrl && (
              <audio controls src={blobUrl} className="w-full border-2 border-black" />
            )}
            <NeoButton variant="ghost" onClick={handleRetry} size="sm">
              ↺ Retry
            </NeoButton>
          </div>
        )}

        {/* Self-rating — visible only after recording */}
        {(phase === "recorded" || phase === "rated") && (
          <div className="space-y-2 border-t-4 border-black pt-3">
            <p className="font-black uppercase text-sm">Rate your performance:</p>
            <div className="grid grid-cols-5 gap-2">
              {[20, 40, 60, 80, 100].map(score => (
                <NeoButton
                  key={score}
                  variant={scores[currentItem.item_id] === score ? "primary" : "ghost"}
                  onClick={() => handleScore(score)}
                  size="md"
                >
                  {score}
                </NeoButton>
              ))}
            </div>
            <p className="text-xs font-medium text-gray-500">20=Poor · 40=Below Avg · 60=Average · 80=Good · 100=Excellent</p>
          </div>
        )}
      </NeoCard>

      {/* Navigation */}
      {phase === "rated" && (
        canSubmit ? (
          <NeoButton className="w-full" onClick={handleSubmit}>Submit Baseline</NeoButton>
        ) : (
          <NeoButton className="w-full" onClick={handleNext}>Next →</NeoButton>
        )
      )}
    </div>
  );
}
