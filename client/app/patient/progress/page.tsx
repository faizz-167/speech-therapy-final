"use client";
import { useEffect, useState } from "react";
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
  BarChart,
  Bar,
} from "recharts";
import { Progress } from "@/types";

const LEVEL_COLORS: Record<string, string> = {
  easy: "bg-neo-accent",
  medium: "bg-neo-secondary",
  advanced: "bg-neo-warning",
};

export default function ProgressPage() {
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Progress>("/patient/progress")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading progress..." />;
  if (data.total_attempts === 0) {
    return (
      <EmptyState
        icon="📈"
        heading="No Progress Yet"
        subtext="Complete your first exercise session to start seeing trends here."
      />
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">My Progress</h1>

      {/* Summary stat cards */}
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

      {/* Weekly trend chart */}
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

      {/* Task performance chart */}
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

      {/* Per-task cards */}
      {data.task_metrics.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-2xl font-black uppercase">My Tasks</h2>
          {data.task_metrics.map((m) => {
            const levelColor = LEVEL_COLORS[m.current_level ?? ""] ?? "bg-white";
            return (
              <NeoCard key={m.task_id} className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <p className="font-black uppercase text-lg leading-tight">{m.task_name}</p>
                  {m.current_level && (
                    <span
                      className={`${levelColor} border-4 border-neo-black px-3 py-1 font-black uppercase text-xs tracking-widest shrink-0`}
                    >
                      {m.current_level}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
                  <div className="border-4 border-neo-black p-2 text-center">
                    <p className="font-black text-xl">{m.total_attempts}</p>
                    <p className="font-black uppercase text-xs text-gray-500">Attempts</p>
                  </div>
                  <div className="border-4 border-neo-black p-2 text-center">
                    <p className="font-black text-xl">{m.overall_accuracy.toFixed(1)}%</p>
                    <p className="font-black uppercase text-xs text-gray-500">Accuracy</p>
                  </div>
                  <div className="border-4 border-neo-black p-2 text-center">
                    <p className="font-black text-xl">{m.pass_rate.toFixed(0)}%</p>
                    <p className="font-black uppercase text-xs text-gray-500">Pass Rate</p>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-3 border-t-4 border-neo-black pt-3">
                  <p className="text-xs font-black uppercase tracking-widest text-gray-500">Last Attempt</p>
                  <span className="border-2 border-neo-black px-2 py-1 text-xs font-black uppercase">
                    {m.last_attempt_result ?? "—"}
                  </span>
                </div>
              </NeoCard>
            );
          })}
        </div>
      )}

      {/* Adaptive progression explanation */}
      <NeoCard className="space-y-4">
        <h2 className="font-black uppercase">How Your Level Changes</h2>
        <div className="grid grid-cols-3 gap-3 text-center text-sm">
          <div className="border-4 border-neo-black bg-neo-secondary p-3 space-y-1">
            <p className="text-2xl font-black">⬆</p>
            <p className="font-black uppercase text-xs">Level Up</p>
            <p className="font-bold">Score ≥ 75</p>
          </div>
          <div className="border-4 border-neo-black bg-white p-3 space-y-1">
            <p className="text-2xl font-black">→</p>
            <p className="font-black uppercase text-xs">Stay</p>
            <p className="font-bold">Score 55–74</p>
          </div>
          <div className="border-4 border-neo-black bg-neo-accent p-3 space-y-1">
            <p className="text-2xl font-black">⬇</p>
            <p className="font-black uppercase text-xs">Level Down</p>
            <p className="font-bold">Score &lt; 55</p>
          </div>
        </div>
        <p className="text-xs font-medium text-gray-500">
          Levels: <strong>Easy → Medium → Advanced</strong>. Your level adjusts after each attempt to keep the challenge appropriate.
        </p>
      </NeoCard>

      {/* Dominant emotion */}
      {data.dominant_emotion && (
        <NeoCard accent="muted" className="space-y-1">
          <p className="font-black uppercase text-sm">Most Common Emotion</p>
          <p className="text-2xl font-black capitalize">{data.dominant_emotion}</p>
        </NeoCard>
      )}
    </div>
  );
}
