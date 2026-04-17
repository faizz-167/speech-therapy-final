"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine,
} from "recharts";
import { Progress } from "@/types";

const LEVEL_ACCENT: Record<string, string> = {
  easy: "bg-neo-secondary border-neo-black",
  medium: "bg-neo-muted border-neo-black",
  advanced: "bg-neo-accent border-neo-black",
  beginner: "bg-neo-secondary border-neo-black",
  intermediate: "bg-neo-muted border-neo-black",
  hard: "bg-neo-accent border-neo-black",
};

function NeoTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
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

function ScoreBar({ value, accent = "bg-neo-accent" }: { value: number; accent?: string }) {
  return (
    <div className="h-2.5 border-2 border-neo-black bg-neo-bg overflow-hidden">
      <div
        className={`h-full ${accent} animate-bar-grow`}
        style={{ "--bar-target": `${Math.min(100, value)}%` } as React.CSSProperties}
      />
    </div>
  );
}

export default function ProgressPage() {
  const { data, error, isLoading } = useQuery<Progress>({
    queryKey: ["patient", "progress"],
    queryFn: () => api.get<Progress>("/patient/progress"),
  });

  if (isLoading) return <LoadingState label="Loading progress..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;
  if (!data || data.total_attempts === 0) {
    return <EmptyState icon="📈" heading="No Progress Yet" subtext="Complete your first exercise session to start seeing trends here." />;
  }

  const taskBarData = data.task_metrics.map((t) => ({
    name: t.task_name.length > 12 ? t.task_name.slice(0, 12) + "…" : t.task_name,
    accuracy: Math.round(t.overall_accuracy),
    passRate: Math.round(t.pass_rate),
  }));

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-5xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="border-b-8 border-neo-black pb-6">
        <div className="inline-block bg-neo-secondary border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-xs mb-3 rotate-1 shadow-neo-sm">Your Stats</div>
        <h1 className="text-5xl font-black uppercase tracking-tighter leading-none">My Progress</h1>
      </div>

      {/* ── KPI STATS ── */}
      <div className="grid grid-cols-3 gap-5">
        {[
          { label: "Attempts", value: data.total_attempts, accent: "bg-neo-secondary" },
          { label: "Avg Score", value: data.avg_final_score.toFixed(1), accent: "bg-white" },
          { label: "Pass Rate", value: `${data.pass_rate.toFixed(0)}%`, accent: "bg-neo-muted" },
        ].map(({ label, value, accent }, i) => (
          <div key={label} className={`border-4 border-neo-black ${accent} shadow-neo-md hover:-translate-y-1 hover:shadow-neo-lg transition-all duration-150 stagger-${i + 1}`}>
            <div className="p-4 text-center">
              <div className="text-5xl font-black leading-none">{value}</div>
              <div className="font-black uppercase tracking-widest text-[10px] mt-3 border-t-4 border-neo-black pt-3">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── EMOTION ── */}
      {data.dominant_emotion && (
        <div className="border-4 border-neo-black bg-neo-muted shadow-neo-sm p-4 flex items-center gap-4 stagger-4">
          <div className="w-12 h-12 border-4 border-neo-black bg-white flex items-center justify-center text-2xl shrink-0">😶</div>
          <div>
            <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/55">Your Most Common Emotion</p>
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
                <ReferenceLine y={75} stroke="#000" strokeDasharray="4 2" strokeOpacity={0.25} label={{ value: "Advance threshold", position: "insideRight", fontSize: 8, fontWeight: 900 }} />
                <Tooltip content={<NeoTooltip />} cursor={{ stroke: "#000", strokeWidth: 1, strokeDasharray: "4 2" }} />
                <Line type="monotone" dataKey="avg_score" name="Avg Score" stroke="#FF6B6B" strokeWidth={3} dot={{ fill: "#FF6B6B", stroke: "#000", strokeWidth: 2, r: 5 }} activeDot={{ r: 7, stroke: "#000", strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── TASK BAR CHART ── */}
      {taskBarData.length > 0 && (
        <div className="border-4 border-neo-black bg-white shadow-neo-md stagger-6">
          <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center gap-2">
            <span className="w-3 h-3 bg-neo-secondary inline-block border-2 border-white"></span>
            Task Performance
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={taskBarData} barSize={28}>
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
            {/* Legend */}
            <div className="flex gap-4 mt-3 text-[10px] font-black uppercase">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-neo-secondary border-2 border-neo-black inline-block"></span> ≥75% Excellent</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-neo-muted border-2 border-neo-black inline-block"></span> 60–74% Good</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-neo-accent border-2 border-neo-black inline-block"></span> &lt;60% Practice</span>
            </div>
          </div>
        </div>
      )}

      {/* ── PER-TASK CARDS ── */}
      {data.task_metrics.length > 0 && (
        <div className="space-y-4">
          <h2 className="font-black uppercase tracking-widest text-sm border-b-4 border-neo-black pb-2">My Tasks</h2>
          {data.task_metrics.map((m, i) => {
            const levelStyle = LEVEL_ACCENT[(m.current_level ?? "").toLowerCase()] ?? "bg-white border-neo-black";
            const pct = Math.round(m.overall_accuracy);
            const barAccent = pct >= 75 ? "bg-neo-secondary" : pct >= 60 ? "bg-neo-muted" : "bg-neo-accent";

            return (
              <div key={m.task_id} className={`border-4 border-neo-black bg-white shadow-neo-sm hover:-translate-y-0.5 hover:shadow-neo-md transition-all duration-150 stagger-${Math.min(i + 1, 6)}`}>
                <div className="p-5 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-black uppercase text-base">{m.task_name}</p>
                      {m.current_level && (
                        <span className={`border-2 px-2 py-0.5 text-[10px] font-black uppercase ${levelStyle}`}>{m.current_level}</span>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-3xl font-black leading-none">{pct}%</p>
                      <p className="text-[10px] font-black uppercase text-neo-black/50">accuracy</p>
                    </div>
                  </div>

                  <ScoreBar value={pct} accent={barAccent} />

                  <div className="grid grid-cols-3 gap-3 text-center border-t-4 border-neo-black pt-3">
                    {[
                      { label: "Attempts", value: m.total_attempts },
                      { label: "Pass Rate", value: `${m.pass_rate.toFixed(0)}%` },
                      { label: "Last", value: m.last_attempt_result ?? "—" },
                    ].map(({ label, value }) => (
                      <div key={label} className="border-2 border-neo-black bg-neo-bg px-2 py-1.5">
                        <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50">{label}</p>
                        <p className="font-black text-sm capitalize">{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── LEVEL PROGRESSION INFO ── */}
      <div className="border-4 border-neo-black bg-white shadow-neo-sm">
        <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm">How Your Level Changes</div>
        <div className="p-5 grid grid-cols-3 gap-3 text-center">
          {[
            { icon: "⬆", label: "Level Up", desc: "Score ≥ 75", accent: "bg-neo-secondary" },
            { icon: "→", label: "Stay", desc: "Score 55–74", accent: "bg-white" },
            { icon: "⬇", label: "Level Down", desc: "Score < 55", accent: "bg-neo-accent" },
          ].map(({ icon, label, desc, accent }) => (
            <div key={label} className={`border-4 border-neo-black ${accent} p-3 space-y-1 hover:-translate-y-0.5 transition-transform`}>
              <p className="text-2xl font-black">{icon}</p>
              <p className="font-black uppercase text-xs">{label}</p>
              <p className="font-bold text-xs">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
