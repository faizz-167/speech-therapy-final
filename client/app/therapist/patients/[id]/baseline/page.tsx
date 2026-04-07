"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { BaselineResult } from "@/types";

export default function TherapistBaselinePage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<BaselineResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<BaselineResult | null>(`/baseline/therapist-view/${id}`)
      .then(setResult).catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load")).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingState label="Loading baseline results..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-6 animate-fade-up max-w-lg">
      <h1 className="text-2xl font-black uppercase">Baseline Results</h1>
      {!result ? (
        <EmptyState
          icon="🧪"
          heading="Baseline Not Completed"
          subtext="This patient has not completed their baseline assessment yet."
        />
      ) : (
        <NeoCard accent="secondary" className="space-y-4">
          <p className="font-black uppercase text-sm">{result.baseline_name}</p>
          <div className="text-5xl font-black">{result.raw_score}<span className="text-xl">/100</span></div>
          <div className="text-xl font-black uppercase border-4 border-black inline-block px-4 py-1">{result.level}</div>
          <p className="text-sm font-medium">Assessed on: {result.assessed_on}</p>
        </NeoCard>
      )}
    </div>
  );
}
