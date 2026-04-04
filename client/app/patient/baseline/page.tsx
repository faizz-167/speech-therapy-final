"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

interface BaselineItem { item_id: string; task_name: string | null; instruction: string | null; display_content: string | null; expected_output: string | null; }
interface BaselineSection { section_id: string; section_name: string; instructions: string | null; items: BaselineItem[]; }
interface BaselineAssessment { baseline_id: string; name: string; domain: string; sections: BaselineSection[]; }

export default function BaselinePage() {
  const [assessments, setAssessments] = useState<BaselineAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentItemIdx, setCurrentItemIdx] = useState(0);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<{ raw_score: number; level: string } | null>(null);

  const allItems = assessments.flatMap(a => a.sections.flatMap(s => s.items.map(i => ({ ...i, baseline_id: a.baseline_id, assessment_name: a.name }))));
  const currentItem = allItems[currentItemIdx];
  const isLast = currentItemIdx === allItems.length - 1;

  useEffect(() => {
    api.get<BaselineAssessment[]>("/baseline/exercises")
      .then(setAssessments)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  function handleScore(score: number) {
    if (!currentItem) return;
    setScores(prev => ({ ...prev, [currentItem.item_id]: score }));
    if (!isLast) setCurrentItemIdx(i => i + 1);
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
    <div className="space-y-6 animate-pop-in max-w-lg">
      <NeoCard accent="secondary" className="space-y-4 text-center">
        <h2 className="text-2xl font-black uppercase">Baseline Complete!</h2>
        <div className="text-5xl font-black">{result.raw_score}<span className="text-2xl">/100</span></div>
        <div className="text-xl font-black uppercase">Level: {result.level}</div>
        <p className="font-medium">Your therapist will now create a personalised therapy plan for you.</p>
        <a href="/patient/home"><NeoButton className="w-full">Go to Home</NeoButton></a>
      </NeoCard>
    </div>
  );

  if (!currentItem) return <ErrorBanner message="No baseline exercises found for your assigned defects." />;

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black uppercase">Baseline Assessment</h1>
        <span className="font-bold text-sm border-4 border-black px-3 py-1">
          {currentItemIdx + 1} / {allItems.length}
        </span>
      </div>
      <div className="w-full bg-gray-200 border-2 border-black h-3">
        <div className="bg-[#FF6B6B] h-full transition-all" style={{ width: `${((currentItemIdx) / allItems.length) * 100}%` }} />
      </div>
      <NeoCard className="space-y-4">
        {currentItem.task_name && <p className="font-black uppercase text-sm text-gray-500">{currentItem.task_name}</p>}
        {currentItem.instruction && <p className="font-bold">{currentItem.instruction}</p>}
        {currentItem.display_content && (
          <div className="border-4 border-black bg-[#FFD93D] p-4 text-xl font-black">{currentItem.display_content}</div>
        )}
        {currentItem.expected_output && <p className="text-sm font-medium text-gray-600">Expected: {currentItem.expected_output}</p>}
      </NeoCard>
      <NeoCard accent="muted" className="space-y-3">
        <p className="font-black uppercase text-sm">Rate your performance:</p>
        <div className="grid grid-cols-5 gap-2">
          {[20, 40, 60, 80, 100].map(score => (
            <NeoButton key={score} variant={scores[currentItem.item_id] === score ? "primary" : "ghost"}
              onClick={() => handleScore(score)} size="md">
              {score}
            </NeoButton>
          ))}
        </div>
        <p className="text-xs font-medium text-gray-500">20=Poor · 40=Below Avg · 60=Average · 80=Good · 100=Excellent</p>
      </NeoCard>
      {isLast && scores[currentItem.item_id] && (
        <NeoButton className="w-full" onClick={handleSubmit}>Submit Baseline</NeoButton>
      )}
    </div>
  );
}
