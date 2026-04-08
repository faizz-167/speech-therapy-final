"use client";
import { useQueries } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { BaselineItemDetail, BaselineResult } from "@/types";

export default function TherapistBaselinePage() {
  const { id } = useParams<{ id: string }>();

  const results = useQueries({
    queries: [
      {
        queryKey: ["therapist", "baseline", id],
        queryFn: () => api.get<BaselineResult | null>(`/baseline/therapist-view/${id}`),
      },
      {
        queryKey: ["therapist", "baseline-items", id],
        queryFn: () => api.get<BaselineItemDetail[]>(`/baseline/therapist-view/${id}/items`).catch(() => [] as BaselineItemDetail[]),
      },
    ],
  });

  const [resultQ, itemsQ] = results;
  const isLoading = results.some((r) => r.isLoading);
  const error = resultQ.error;

  if (isLoading) return <LoadingState label="Loading baseline results..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  const result = resultQ.data ?? null;
  const items = itemsQ.data ?? [];

  return (
    <div className="space-y-6 animate-fade-up max-w-4xl">
      <h1 className="text-2xl font-black uppercase">Baseline Results</h1>
      {!result ? (
        <EmptyState
          icon="🧪"
          heading="Baseline Not Completed"
          subtext="This patient has not completed their baseline assessment yet."
        />
      ) : (
        <>
          <NeoCard accent="secondary" className="space-y-4">
            <p className="font-black uppercase text-sm">{result.baseline_name}</p>
            <div className="text-5xl font-black">{result.raw_score}<span className="text-xl">/100</span></div>
            <div className="flex flex-wrap gap-3 items-center">
              <div className="text-xl font-black uppercase border-4 border-black inline-block px-4 py-1">{result.level}</div>
              <p className="text-sm font-medium">Assessed on: {result.assessed_on}</p>
            </div>
          </NeoCard>

          <div className="space-y-4">
            <h2 className="text-lg font-black uppercase tracking-widest">Item Breakdown</h2>
            {items.length === 0 ? (
              <EmptyState
                icon="📋"
                heading="No Item Results"
                subtext="The completed baseline does not have any item-level results yet."
              />
            ) : (
              <div className="grid gap-4">
                {items.map((item, index) => (
                  <NeoCard key={item.item_id} className="space-y-3">
                    <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <p className="text-xs font-black uppercase tracking-widest text-gray-500">Item {index + 1}</p>
                        <p className="font-black text-lg">{item.prompt_text ?? "Untitled baseline item"}</p>
                      </div>
                      <span className={`border-4 border-neo-black px-3 py-1 text-sm font-black uppercase ${item.pass_fail ? "bg-neo-primary text-neo-black" : "bg-neo-warning text-neo-black"}`}>
                        {item.pass_fail ? "Pass" : "Needs Work"}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                      <div className="border-4 border-neo-black bg-white px-4 py-3">
                        <p className="text-xs font-black uppercase tracking-widest text-gray-500">Final Score</p>
                        <p className="text-2xl font-black">{item.final_score}</p>
                      </div>
                      <div className="border-4 border-neo-black bg-white px-4 py-3">
                        <p className="text-xs font-black uppercase tracking-widest text-gray-500">Phoneme Accuracy</p>
                        <p className="text-2xl font-black">{item.phoneme_accuracy ?? "—"}</p>
                      </div>
                      <div className="border-4 border-neo-black bg-white px-4 py-3">
                        <p className="text-xs font-black uppercase tracking-widest text-gray-500">Fluency Score</p>
                        <p className="text-2xl font-black">{item.fluency_score ?? "—"}</p>
                      </div>
                    </div>

                    <div className="border-4 border-neo-black bg-neo-secondary/40 px-4 py-3">
                      <p className="text-xs font-black uppercase tracking-widest text-gray-500">Transcript</p>
                      <p className="font-medium">{item.transcript ?? "Transcript not available for this completed baseline result."}</p>
                    </div>
                  </NeoCard>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
