"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";

interface Progress {
  total_attempts: number;
  avg_final_score: number;
  pass_rate: number;
  weekly_trend: { week: string; avg_score: number; attempts: number }[];
  task_metrics: {
    task_name: string;
    overall_accuracy: number;
    total_attempts: number;
    current_level: string | null;
  }[];
  dominant_emotion: string | null;
}

export default function ProgressPage() {
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Progress>("/patient/progress")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBanner message={error} />;
  if (!data) return <SkeletonList />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">My Progress</h1>

      <div className="grid grid-cols-3 gap-4">
        <NeoCard accent="secondary" className="text-center">
          <div className="text-3xl font-black">{data.total_attempts}</div>
          <div className="text-xs font-black uppercase">Attempts</div>
        </NeoCard>
        <NeoCard accent="default" className="text-center">
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
          <h2 className="font-black uppercase">Weekly Score Trend</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.weekly_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="avg_score"
                stroke="#FF6B6B"
                strokeWidth={3}
                dot={{ fill: "#FF6B6B", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </NeoCard>
      )}

      {data.task_metrics.length > 0 && (
        <NeoCard className="space-y-3">
          <h2 className="font-black uppercase">Task Performance</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.task_metrics}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="task_name" tick={{ fontSize: 8 }} />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="overall_accuracy" fill="#FFD93D" stroke="#000" strokeWidth={2} />
            </BarChart>
          </ResponsiveContainer>
        </NeoCard>
      )}

      {data.dominant_emotion && (
        <NeoCard accent="muted" className="space-y-1">
          <p className="font-black uppercase text-sm">Most Common Emotion</p>
          <p className="text-2xl font-black capitalize">{data.dominant_emotion}</p>
        </NeoCard>
      )}
    </div>
  );
}
