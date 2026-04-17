"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Progress } from "@/types";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine,
} from "recharts";

const LEVEL_STYLES: Record<string, string> = {
  beginner: "bg-neo-secondary border-neo-black text-neo-black",
  elementary: "bg-neo-secondary border-neo-black text-neo-black",
  intermediate: "bg-neo-muted border-neo-black text-neo-black",
  advanced: "bg-neo-accent border-neo-black text-neo-black",
  expert: "bg-neo-accent border-neo-black text-neo-black",
  easy: "bg-neo-secondary border-neo-black text-neo-black",
  medium: "bg-neo-muted border-neo-black text-neo-black",
  hard: "bg-neo-accent border-neo-black text-neo-black",
};

function NeoTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string; color?: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-4 border-neo-black bg-white shadow-neo-sm p-3 font-black text-xs">
      <p className="uppercase tracking-widest text-neo-black/50 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="uppercase">{p.name}: <span className="text-neo-accent">{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</span></p>
      ))}
    </div>
  );
}

export default function TherapistPatientProgressPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isLoading } = useQuery<Progress>({
    queryKey: ["therapist", "patient-progress", id],
    queryFn: () => api.get<Progress>(`/therapist/patients/${id}/progress`),
  });

  if (isLoading) return <LoadingState label="Loading patient progress..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;
  if (!data || data.total_attempts === 0) return (
    <EmptyState icon="📉" heading="No Progress Data Yet" subtext="This patient has not completed any scored attempts." />
  );

  const taskBarData = data.task_metrics.map((t) => ({
    name: t.task_name.length > 14 ? t.task_name.slice(0, 14) + "…" : t.task_name,
    accuracy: Math.round(t.overall_accuracy),
    passRate: Math.round(t.pass_rate),
  }));

  return (
    <div className="animate-fade-up p-4 md:p-6 max-w-5xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="flex items-center gap-4 border-b-8 border-neo-black pb-6">
        <Link href={`/therapist/patients/${id}`} className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-xs tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-0.5 active:translate-y-0.5 active:shadow-none shrink-0">
          ← Back
        </Link>
        <div>
          <div className="inline-block bg-neo-secondary border-4 border-neo-black px-3 py-0.5 font-black uppercase tracking-widest text-xs mb-1 rotate-1 shadow-neo-sm">Analytics</div>
          <h1 className="text-4xl font-black uppercase tracking-tighter leading-none">Patient Progress</h1>
        </div>
      </div>

      {/* ── KPI STATS ── */}
      <div className="grid grid-cols-3 gap-5">
        {[
          { label: "Total Attempts", value: data.total_attempts, accent: "bg-neo-secondary" },
          { label: "Avg Score", value: data.avg_final_score.toFixed(1), accent: "bg-white" },
          { label: "Pass Rate", value: `${data.pass_rate.toFixed(0)}%`, accent: "bg-neo-muted" },
        ].map(({ label, value, accent }, i) => (
          <div key={label} className={`border-4 border-neo-black ${accent} shadow-neo-md hover:-translate-y-1 hover:shadow-neo-lg transition-all duration-150 stagger-${i + 1}`}>
            <div className="p-5 text-center">
              <div className="text-5xl font-black leading-none">{value}</div>
              <div className="font-black uppercase tracking-widest text-xs mt-3 border-t-4 border-neo-black pt-3">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── EMOTION ── */}
      {data.dominant_emotion && (
        <div className="border-4 border-neo-black bg-neo-accent shadow-neo-sm p-4 flex items-center gap-4 stagger-4">
          <div className="w-12 h-12 border-4 border-neo-black bg-white flex items-center justify-center text-2xl shrink-0">😶</div>
          <div>
            <p className="font-black uppercase text-xs tracking-widest text-neo-black/60">Dominant Emotion During Sessions</p>
            <p className="font-black text-xl uppercase">{data.dominant_emotion}</p>
          </div>
        </div>
      )}

      {/* ── WEEKLY TREND ── */}
      {data.weekly_trend.length > 0 && (
        <div className="border-4 border-neo-black bg-white shadow-neo-md stagger-5">
          <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center gap-2">
            <span className="w-3 h-3 bg-neo-accent inline-block border-2 border-white"></span>
            Weekly Score Trend
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.weekly_trend}>
                <CartesianGrid strokeDasharray="0" stroke="#000" strokeOpacity={0.07} />
                <XAxis dataKey="week" tick={{ fontSize: 10, fontWeight: 900, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fontWeight: 700, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} width={28} />
                <ReferenceLine y={75} stroke="#000" strokeDasharray="4 2" strokeOpacity={0.3} label={{ value: "Advance", position: "right", fontSize: 9, fontWeight: 900, fontFamily: "Space Grotesk" }} />
                <Tooltip content={<NeoTooltip />} cursor={{ stroke: "#000", strokeWidth: 1, strokeDasharray: "4 2" }} />
                <Line type="monotone" dataKey="avg_score" name="Avg Score" stroke="#FF6B6B" strokeWidth={3} dot={{ fill: "#FF6B6B", stroke: "#000", strokeWidth: 2, r: 5 }} activeDot={{ r: 7, stroke: "#000", strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── TASK ACCURACY BAR CHART ── */}
      {taskBarData.length > 0 && (
        <div className="border-4 border-neo-black bg-white shadow-neo-md stagger-6">
          <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center gap-2">
            <span className="w-3 h-3 bg-neo-secondary inline-block border-2 border-white"></span>
            Task Accuracy
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={taskBarData} barSize={32}>
                <CartesianGrid strokeDasharray="0" stroke="#000" strokeOpacity={0.07} vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 9, fontWeight: 900, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fontWeight: 700, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} width={24} />
                <Tooltip content={<NeoTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
                <Bar dataKey="accuracy" name="Accuracy %" stroke="#000" strokeWidth={2} radius={0}>
                  {taskBarData.map((entry, index) => (
                    <Cell key={index} fill={entry.accuracy >= 75 ? "#FFD93D" : entry.accuracy >= 60 ? "#C4B5FD" : "#FF6B6B"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── PER-TASK CARDS ── */}
      <div className="space-y-3">
        <h2 className="font-black uppercase tracking-widest text-sm border-b-4 border-neo-black pb-2">Task Details</h2>
        {data.task_metrics.map((t, i) => {
          const levelKey = (t.current_level ?? "").toLowerCase();
          const levelStyle = LEVEL_STYLES[levelKey] ?? "bg-white border-neo-black text-neo-black";
          const trend = t.last_attempt_result === "pass" ? "↑" : t.last_attempt_result === "fail" ? "↓" : null;
          const trendColor = t.last_attempt_result === "pass" ? "text-green-700" : "text-red-600";
          const pct = Math.round(t.overall_accuracy);

          return (
            <div key={t.task_id} className={`border-4 border-neo-black bg-white shadow-neo-sm hover:-translate-y-0.5 hover:shadow-neo-md transition-all duration-150 stagger-${Math.min(i + 1, 6)}`}>
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <p className="font-black uppercase text-sm">{t.task_name}</p>
                    {trend && <span className={`font-black text-base ${trendColor}`}>{trend}</span>}
                    {t.current_level && (
                      <span className={`border-2 px-2 py-0.5 text-[10px] font-black uppercase ${levelStyle}`}>
                        {t.current_level}
                      </span>
                    )}
                  </div>
                  {/* Mini progress bar */}
                  <div className="h-2 border-2 border-neo-black bg-neo-bg overflow-hidden max-w-xs">
                    <div
                      className={`h-full animate-bar-grow ${pct >= 75 ? "bg-neo-secondary" : pct >= 60 ? "bg-neo-muted" : "bg-neo-accent"}`}
                      style={{ "--bar-target": `${pct}%` } as React.CSSProperties}
                    />
                  </div>
                  <p className="text-[10px] font-bold text-neo-black/50 mt-1">{t.total_attempts} attempt{t.total_attempts !== 1 ? "s" : ""}</p>
                </div>
                <div className="text-right ml-4 shrink-0">
                  <div className="text-3xl font-black">{pct}%</div>
                  <div className="text-[10px] font-black uppercase text-neo-black/50">accuracy</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
