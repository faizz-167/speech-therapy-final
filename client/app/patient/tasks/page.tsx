"use client";
import { useQueries } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { HomeSummary, TodayTasksResponse } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import Link from "next/link";

const TASK_MODE_ICONS: Record<string, string> = {
  reading: "📖",
  listening: "👂",
  speaking: "🎤",
  repeating: "🔄",
  matching: "🔗",
};

const LEVEL_ACCENT: Record<string, string> = {
  beginner: "bg-neo-secondary border-neo-black",
  elementary: "bg-neo-secondary border-neo-black",
  intermediate: "bg-neo-muted border-neo-black",
  advanced: "bg-neo-accent border-neo-black",
  expert: "bg-neo-accent border-neo-black",
  easy: "bg-neo-secondary border-neo-black",
  medium: "bg-neo-muted border-neo-black",
  hard: "bg-neo-accent border-neo-black",
};

export default function TasksPage() {
  const results = useQueries({
    queries: [
      { queryKey: ["patient", "tasks"], queryFn: () => api.get<TodayTasksResponse>("/patient/tasks"), refetchOnWindowFocus: true, refetchInterval: 15000 },
      { queryKey: ["patient", "home"], queryFn: () => api.get<HomeSummary>("/patient/home").catch(() => null), refetchOnWindowFocus: true, refetchInterval: 15000 },
    ],
  });

  const [tasksQ, homeQ] = results;
  const isLoading = results.some((r) => r.isLoading);
  const error = tasksQ.error;

  if (isLoading) return <LoadingState label="Loading your tasks..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  const tasks = tasksQ.data?.assignments ?? [];
  const anyEscalated = tasksQ.data?.any_escalated ?? false;
  const homeSummary = homeQ.data ?? null;
  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const allCompleted = tasks.length > 0 && completedCount === tasks.length;

  const day = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-4xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="border-b-8 border-neo-black pb-6">
        <div className="inline-block bg-neo-accent border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-xs mb-3 rotate-1 shadow-neo-sm">
          {day}
        </div>
        <div className="flex items-end justify-between">
          <h1 className="text-5xl font-black uppercase tracking-tighter leading-none">Today&apos;s Tasks</h1>
          {tasks.length > 0 && (
            <div className="border-4 border-neo-black bg-white px-4 py-2 shadow-neo-sm text-right">
              <p className="font-black text-3xl leading-none">{completedCount}<span className="text-xl text-neo-black/40">/{tasks.length}</span></p>
              <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50">done</p>
            </div>
          )}
        </div>

        {/* Progress bar */}
        {tasks.length > 0 && (
          <div className="mt-4 h-4 border-4 border-neo-black bg-neo-bg overflow-hidden">
            <div
              className="h-full bg-neo-accent animate-bar-grow transition-all duration-500"
              style={{ "--bar-target": `${Math.round((completedCount / tasks.length) * 100)}%` } as React.CSSProperties}
            />
          </div>
        )}
      </div>

      {/* ── ESCALATION WARNING ── */}
      {anyEscalated && (
        <div className="border-4 border-neo-black bg-neo-secondary shadow-neo-sm p-5 flex items-center gap-4 stagger-1">
          <div className="w-10 h-10 border-4 border-neo-black bg-neo-black text-white flex items-center justify-center font-black text-lg shrink-0">!</div>
          <div>
            <p className="font-black uppercase text-sm">Tasks Locked For Review</p>
            <p className="font-medium text-sm text-neo-black/70">Your therapist is reviewing an escalated plan. Check back once approved.</p>
          </div>
        </div>
      )}

      {/* ── STATES ── */}
      {anyEscalated ? (
        <EmptyState icon="🔒" heading="Tasks Locked For Review" subtext="Your therapist is reviewing a regenerated plan. You can continue once it&apos;s approved." />
      ) : allCompleted ? (
        <div className="border-8 border-neo-black bg-neo-secondary shadow-neo-xl p-10 text-center space-y-4">
          <div className="text-6xl animate-pop-in">🎉</div>
          <h2 className="text-4xl font-black uppercase tracking-tighter">All Done!</h2>
          <p className="font-bold text-xl">Every task is complete. Excellent work today!</p>
        </div>
      ) : tasks.length === 0 && !homeSummary?.has_approved_plan ? (
        <EmptyState icon="📋" heading="No Plan Yet" subtext="Your therapist hasn&apos;t approved a plan yet. Check back soon." />
      ) : tasks.length === 0 ? (
        <EmptyState icon="📭" heading="No Tasks Today" subtext="No tasks are scheduled for today — check back tomorrow." />
      ) : (
        <div className="space-y-4">
          {tasks.map((t, i) => {
            const isCompleted = t.status === "completed";
            const modeIcon = TASK_MODE_ICONS[(t.task_mode ?? "").toLowerCase()] ?? "🎤";
            const levelStyle = LEVEL_ACCENT[(t.current_level ?? "").toLowerCase()] ?? "bg-white border-neo-black";

            return (
              <div
                key={t.assignment_id}
                className={`border-4 border-neo-black shadow-neo-sm transition-all duration-200 stagger-${Math.min(i + 1, 6)} ${
                  isCompleted
                    ? "bg-neo-secondary opacity-80"
                    : "bg-white hover:-translate-y-0.5 hover:shadow-neo-md"
                }`}
              >
                <div className="flex items-center gap-4 p-4">
                  {/* Mode icon */}
                  <div className={`w-12 h-12 border-4 border-neo-black flex items-center justify-center text-2xl shrink-0 ${isCompleted ? "bg-neo-black" : "bg-neo-bg"}`}>
                    {isCompleted ? <span className="text-white font-black text-lg">✓</span> : modeIcon}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className={`font-black uppercase text-base leading-tight ${isCompleted ? "line-through text-neo-black/50" : ""}`}>
                      {t.task_name}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                      {t.task_mode && (
                        <span className="border-2 border-neo-black bg-white px-2 py-0.5 text-[10px] font-black uppercase">
                          {t.task_mode}
                        </span>
                      )}
                      {t.current_level && (
                        <span className={`border-2 px-2 py-0.5 text-[10px] font-black uppercase ${levelStyle}`}>
                          {t.current_level}
                        </span>
                      )}
                      <span className={`border-2 border-neo-black px-2 py-0.5 text-[10px] font-black uppercase ${
                        isCompleted ? "bg-neo-black text-white" : "bg-neo-bg"
                      }`}>
                        {t.status}
                      </span>
                    </div>
                  </div>

                  {/* Action */}
                  {!isCompleted && !anyEscalated && (
                    <Link href={`/patient/tasks/${t.assignment_id}`} className="shrink-0">
                      <NeoButton size="sm" className="whitespace-nowrap">
                        Start →
                      </NeoButton>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
