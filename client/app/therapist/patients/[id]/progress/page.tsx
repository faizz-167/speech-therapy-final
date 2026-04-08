"use client";
import { useQuery } from "@tanstack/react-query";
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

  const { data, error, isLoading } = useQuery<Progress>({
    queryKey: ["therapist", "patient-progress", id],
    queryFn: () => api.get<Progress>(`/therapist/patients/${id}/progress`),
  });

  if (isLoading) return <LoadingState label="Loading patient progress..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;
  if (!data || data.total_attempts === 0) {
    return (
      <EmptyState
        icon="📉"
        heading="No Progress Data Yet"
        subtext="This patient has not completed any scored attempts."
      />
    );
  }

  const levelColors: Record<string, string> = {
    beginner: "bg-green-100 border-green-700 text-green-800",
    elementary: "bg-lime-100 border-lime-700 text-lime-800",
    intermediate: "bg-yellow-100 border-yellow-700 text-yellow-800",
    advanced: "bg-red-100 border-red-700 text-red-800",
    expert: "bg-purple-100 border-purple-700 text-purple-800",
  };

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

      {data.dominant_emotion && (
        <NeoCard accent="accent" className="flex items-center gap-4">
          <div className="text-3xl">😶</div>
          <div>
            <p className="font-black uppercase text-sm">Emotion &amp; Engagement</p>
            <p className="text-xs font-medium text-gray-600">
              Dominant emotion: <span className="font-black uppercase">{data.dominant_emotion}</span>
            </p>
          </div>
        </NeoCard>
      )}

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
        {data.task_metrics.map((t) => {
          const levelKey = (t.current_level ?? "").toLowerCase();
          const levelClass = levelColors[levelKey] ?? "bg-gray-100 border-gray-400 text-gray-700";
          const trend = t.last_attempt_result === "pass" ? "↑" : t.last_attempt_result === "fail" ? "↓" : null;
          const trendColor = t.last_attempt_result === "pass" ? "text-green-700" : "text-red-600";
          return (
            <NeoCard key={t.task_id} className="flex items-center justify-between">
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <p className="font-black uppercase text-sm">{t.task_name}</p>
                  {trend && <span className={`font-black text-lg ${trendColor}`}>{trend}</span>}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-xs font-medium text-gray-500">{t.total_attempts} attempts</p>
                  {t.current_level && (
                    <span className={`border-2 px-2 py-0.5 text-xs font-black uppercase ${levelClass}`}>
                      {t.current_level}
                    </span>
                  )}
                </div>
              </div>
              <div className="text-2xl font-black">{t.overall_accuracy.toFixed(0)}%</div>
            </NeoCard>
          );
        })}
      </div>
    </div>
  );
}
