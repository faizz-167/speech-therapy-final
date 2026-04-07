"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Progress } from "@/types";

export default function TherapistPatientProgressPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Progress>(`/therapist/patients/${id}/progress`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading patient progress..." />;
  if (data.total_attempts === 0) {
    return (
      <EmptyState
        icon="📉"
        heading="No Progress Data Yet"
        subtext="This patient has not completed any scored attempts."
      />
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-2xl font-black uppercase">Patient Progress</h1>

      <div className="grid grid-cols-3 gap-4">
        <NeoCard accent="secondary" className="text-center">
          <div className="text-3xl font-black">{data.total_attempts}</div>
          <div className="text-xs font-black uppercase">Attempts</div>
        </NeoCard>
        <NeoCard className="text-center">
          <div className="text-3xl font-black">{data.avg_final_score.toFixed(1)}</div>
          <div className="text-xs font-black uppercase">Avg Score</div>
        </NeoCard>
        <NeoCard accent="muted" className="text-center">
          <div className="text-3xl font-black">{data.pass_rate.toFixed(0)}%</div>
          <div className="text-xs font-black uppercase">Pass Rate</div>
        </NeoCard>
      </div>

      {data.weekly_trend.length > 0 && (
        <NeoCard className="space-y-3">
          <h2 className="font-black uppercase">Weekly Trend</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.weekly_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="avg_score" stroke="#FF6B6B" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </NeoCard>
      )}

      <div className="space-y-3">
        <h2 className="font-black uppercase">Task Breakdown</h2>
        {data.task_metrics.map((t) => (
          <NeoCard key={t.task_name} className="flex items-center justify-between">
            <div>
              <p className="font-black uppercase text-sm">{t.task_name}</p>
              <p className="text-xs font-medium text-gray-500">
                {t.total_attempts} attempts · Level: {t.current_level ?? "—"}
              </p>
            </div>
            <div className="text-2xl font-black">{t.overall_accuracy.toFixed(0)}%</div>
          </NeoCard>
        ))}
      </div>
    </div>
  );
}
