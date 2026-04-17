"use client";
import { useQueries } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { BaselineItemDetail, BaselineResult } from "@/types";
import Link from "next/link";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";

function ScoreBar({ label, value, max = 100, accent = "bg-neo-accent" }: {
  label: string; value: number | null | undefined; max?: number; accent?: string;
}) {
  const pct = value != null ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/60">{label}</p>
        <p className="font-black text-sm">{value != null ? (typeof value === "number" && label.includes("WPM") ? value.toFixed(1) : `${value.toFixed != null ? (value as number).toFixed(1) : value}`) : "—"}</p>
      </div>
      <div className="h-3 border-2 border-neo-black bg-neo-bg overflow-hidden">
        <div
          className={`h-full ${accent} animate-bar-grow`}
          style={{ "--bar-target": `${pct}%` } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

function NeoTooltip({ active, payload }: { active?: boolean; payload?: Array<{ value: number; name: string }> }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-4 border-neo-black bg-white shadow-neo-sm p-2 font-black text-xs">
      {payload.map((p, i) => <p key={i} className="uppercase">{p.name}: {p.value}</p>)}
    </div>
  );
}

export default function TherapistBaselinePage() {
  const { id } = useParams<{ id: string }>();

  const results = useQueries({
    queries: [
      { queryKey: ["therapist", "baseline", id], queryFn: () => api.get<BaselineResult | null>(`/baseline/therapist-view/${id}`) },
      { queryKey: ["therapist", "baseline-items", id], queryFn: () => api.get<BaselineItemDetail[]>(`/baseline/therapist-view/${id}/items`).catch(() => [] as BaselineItemDetail[]) },
    ],
  });

  const [resultQ, itemsQ] = results;
  const isLoading = results.some((r) => r.isLoading);
  const error = resultQ.error;

  if (isLoading) return <LoadingState label="Loading baseline results..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  const result = resultQ.data ?? null;
  const items = itemsQ.data ?? [];

  const levelAccent: Record<string, string> = {
    beginner: "bg-neo-secondary",
    elementary: "bg-neo-secondary",
    intermediate: "bg-neo-muted",
    advanced: "bg-neo-accent",
    expert: "bg-neo-accent",
    easy: "bg-neo-secondary",
    medium: "bg-neo-muted",
    hard: "bg-neo-accent",
  };

  // Build radar data from first item that has all fields
  const sampleItem = items.find((it) => it.word_accuracy != null);
  const radarData = sampleItem ? [
    { metric: "Word Acc", value: Math.round((sampleItem.word_accuracy ?? 0) * 100) / 100 },
    { metric: "Phoneme", value: Math.round((sampleItem.phoneme_accuracy ?? 0) * 100) / 100 },
    { metric: "Fluency", value: sampleItem.fluency_score ?? 0 },
    { metric: "Confidence", value: sampleItem.confidence_score ?? 0 },
    { metric: "Engagement", value: sampleItem.engagement_score ?? 0 },
    { metric: "Emotion", value: sampleItem.emotion_score ?? 0 },
  ] : [];

  return (
    <div className="animate-fade-up p-4 md:p-6 max-w-5xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="flex items-center gap-4 border-b-8 border-neo-black pb-6">
        <Link href={`/therapist/patients/${id}`} className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-xs tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-0.5 active:translate-y-0.5 active:shadow-none shrink-0">
          ← Back
        </Link>
        <div>
          <div className="inline-block bg-neo-muted border-4 border-neo-black px-3 py-0.5 font-black uppercase tracking-widest text-xs mb-1 -rotate-1 shadow-neo-sm">
            Assessment
          </div>
          <h1 className="text-4xl font-black uppercase tracking-tighter leading-none">Baseline Results</h1>
        </div>
      </div>

      {!result ? (
        <EmptyState icon="🧪" heading="Baseline Not Completed" subtext="This patient has not completed their baseline assessment yet." />
      ) : (
        <>
          {/* ── SCORE HERO ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className={`border-4 border-neo-black shadow-neo-md p-6 text-center ${levelAccent[(result.level ?? "").toLowerCase()] ?? "bg-neo-secondary"} col-span-1`}>
              <p className="font-black uppercase text-xs tracking-widest text-neo-black/60 mb-2">{result.baseline_name}</p>
              <div className="text-8xl font-black leading-none animate-score-slam">{result.raw_score}</div>
              <div className="text-lg font-black opacity-60">/100</div>
              <div className="mt-4 border-4 border-neo-black bg-neo-black text-white px-4 py-1 font-black uppercase tracking-widest text-sm inline-block">
                {result.level}
              </div>
              <p className="text-xs font-medium mt-3 text-neo-black/60">Assessed: {result.assessed_on}</p>
            </div>

            {/* Radar chart */}
            {radarData.length > 0 && (
              <div className="col-span-2 border-4 border-neo-black bg-white shadow-neo-md p-4">
                <p className="font-black uppercase text-xs tracking-widest mb-2 text-neo-black/60">Score Profile</p>
                <ResponsiveContainer width="100%" height={200}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#000" strokeOpacity={0.12} />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fontWeight: 900, fontFamily: "Space Grotesk", fill: "#000" }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar name="Score" dataKey="value" stroke="#000" strokeWidth={2} fill="#C4B5FD" fillOpacity={0.65} dot={{ fill: "#000", r: 3 }} />
                    <Tooltip content={<NeoTooltip />} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* ── ITEM BREAKDOWN ── */}
          <div className="space-y-4">
            <h2 className="font-black uppercase tracking-widest text-sm border-b-4 border-neo-black pb-2">Item Breakdown ({items.length})</h2>

            {items.length === 0 ? (
              <EmptyState icon="📋" heading="No Item Results" subtext="The completed baseline does not have any item-level results yet." />
            ) : (
              <div className="space-y-4">
                {items.map((item, index) => (
                  <div key={item.item_id} className={`border-4 border-neo-black bg-white shadow-neo-sm stagger-${Math.min(index + 1, 6)}`}>
                    {/* Item header */}
                    <div className={`border-b-4 border-neo-black px-5 py-3 flex items-start justify-between gap-4 ${item.pass_fail ? "bg-neo-secondary" : "bg-neo-accent"}`}>
                      <div>
                        <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-0.5">Item {index + 1}</p>
                        <p className="font-black text-base leading-tight">{item.prompt_text ?? "Untitled baseline item"}</p>
                      </div>
                      <div className="border-4 border-neo-black bg-white px-3 py-1 font-black uppercase text-xs tracking-widest shrink-0 shadow-neo-sm">
                        {item.pass_fail ? "✓ Pass" : "✗ Needs Work"}
                      </div>
                    </div>

                    {/* Score bars */}
                    <div className="p-5 space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <ScoreBar label="Word Accuracy" value={item.word_accuracy} accent="bg-neo-secondary" />
                        <ScoreBar label="Phoneme Accuracy" value={item.phoneme_accuracy} accent="bg-neo-muted" />
                        <ScoreBar label="Fluency Score" value={item.fluency_score} accent="bg-neo-accent" />
                        <ScoreBar label="Confidence" value={item.confidence_score} accent="bg-neo-secondary" />
                        <ScoreBar label="Emotion Score" value={item.emotion_score} accent="bg-neo-muted" />
                        <ScoreBar label="Engagement" value={item.engagement_score} accent="bg-neo-accent" />
                      </div>

                      {/* Extra metrics row */}
                      <div className="grid grid-cols-3 gap-3 border-t-4 border-neo-black pt-3">
                        {[
                          { label: "Final Score", value: item.final_score?.toFixed(1) },
                          { label: "Speech Rate WPM", value: item.speech_rate_wpm?.toFixed(1) },
                          { label: "Dominant Emotion", value: item.dominant_emotion ?? "—" },
                        ].map(({ label, value }) => (
                          <div key={label} className="border-2 border-neo-black px-3 py-2 text-center bg-neo-bg">
                            <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">{label}</p>
                            <p className="font-black text-base capitalize">{value ?? "—"}</p>
                          </div>
                        ))}
                      </div>

                      {/* Transcript */}
                      {item.transcript && (
                        <div className="border-4 border-neo-black bg-neo-muted/30 px-4 py-3">
                          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">Transcript</p>
                          <p className="font-medium text-sm italic">&ldquo;{item.transcript}&rdquo;</p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
