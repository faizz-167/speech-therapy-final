"use client";
import { useQueries } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import Link from "next/link";
import { BaselineResult, HomeData, PatientProfile, TodayTasksResponse } from "@/types";

function formatPlanDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function StreakFire({ count }: { count: number }) {
  return (
    <div className="relative">
      <div className="text-5xl">{count > 0 ? "🔥" : "💧"}</div>
      <div className="absolute -bottom-1 -right-2 border-2 border-neo-black bg-neo-secondary px-1.5 py-0.5 font-black text-[10px] leading-none">
        {count}
      </div>
    </div>
  );
}

export default function PatientHomePage() {
  const results = useQueries({
    queries: [
      { queryKey: ["patient", "home"], queryFn: () => api.get<HomeData>("/patient/home"), refetchOnWindowFocus: true, refetchInterval: 15000 },
      { queryKey: ["patient", "profile"], queryFn: () => api.get<PatientProfile>("/patient/profile").catch(() => null), refetchOnWindowFocus: true },
      {
        queryKey: ["patient", "tasks"],
        queryFn: () => api.get<TodayTasksResponse>("/patient/tasks").catch(() => ({ assignments: [], any_escalated: false })),
        refetchOnWindowFocus: true,
        refetchInterval: 15000,
      },
      { queryKey: ["patient", "baseline-result"], queryFn: () => api.get<BaselineResult | null>("/baseline/result").catch(() => null), refetchOnWindowFocus: true },
    ],
  });

  const [homeQ, profileQ, tasksQ, baselineQ] = results;
  const isLoading = results.some((r) => r.isLoading);
  const mainError = homeQ.error;

  if (isLoading) return <LoadingState label="Loading your home screen..." />;
  if (mainError) return <ErrorState message={mainError instanceof Error ? mainError.message : "Failed to load"} />;
  if (!homeQ.data) return <LoadingState label="Loading your home screen..." />;

  const data = homeQ.data;
  const profile = profileQ.data ?? null;
  const tasks = tasksQ.data?.assignments ?? [];
  const baseline = baselineQ.data ?? null;

  const completedTasks = tasks.filter((t) => t.status === "completed").length;
  const totalTasks = tasks.length;
  const allTasksDone = data.has_approved_plan && totalTasks > 0 && completedTasks === totalTasks;
  const taskPct = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  const firstName = data.full_name?.split(" ")[0] ?? "";

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-5xl mx-auto space-y-10">

      {/* ── GREETING ── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end border-b-8 border-neo-black pb-6">
        <div>
          <div className="inline-block bg-neo-secondary border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-xs mb-3 -rotate-1 shadow-neo-sm">
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </div>
          <h1 className="text-4xl md:text-6xl font-black uppercase tracking-tighter leading-none">
            {firstName ? `Hey,\n${firstName}!` : "Welcome Back!"}
          </h1>
        </div>
        {profile?.current_streak != null && profile.current_streak > 0 && (
          <div className="mt-4 sm:mt-0 border-4 border-neo-black bg-neo-accent px-5 py-3 shadow-neo-sm rotate-1">
            <div className="flex items-center gap-3">
              <StreakFire count={profile.current_streak} />
              <div>
                <p className="font-black text-2xl leading-none">{profile.current_streak}</p>
                <p className="font-black uppercase text-[10px] tracking-widest">Day Streak</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── SUMMARY STATS ── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { value: profile?.current_streak ?? 0, label: "Streak", accent: "bg-neo-accent", icon: "🔥" },
          { value: data.today_tasks, label: "Tasks Today", accent: "bg-neo-secondary", icon: "📋" },
          { value: baseline?.level ? baseline.level.toUpperCase() : "—", label: "Baseline Level", accent: "bg-neo-muted", icon: "🧭" },
        ].map(({ value, label, accent, icon }, i) => (
          <div key={label} className={`border-4 border-neo-black ${accent} shadow-neo-sm hover:-translate-y-0.5 hover:shadow-neo-md transition-all duration-150 stagger-${i + 1}`}>
            <div className="p-4 text-center">
              <div className="text-2xl mb-1">{icon}</div>
              <div className="text-3xl font-black leading-none">{value}</div>
              <div className="font-black uppercase text-[10px] tracking-widest mt-2">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── TASK PROGRESS BAR (when has plan) ── */}
      {data.has_approved_plan && totalTasks > 0 && (
        <div className="border-4 border-neo-black bg-white shadow-neo-sm p-5 stagger-4">
          <div className="flex items-center justify-between mb-3">
            <p className="font-black uppercase text-sm tracking-widest">Today&apos;s Progress</p>
            <p className="font-black text-2xl">{completedTasks}<span className="text-sm text-neo-black/50">/{totalTasks}</span></p>
          </div>
          <div className="h-5 border-4 border-neo-black bg-neo-bg overflow-hidden">
            <div
              className="h-full bg-neo-accent animate-bar-grow flex items-center justify-end pr-2"
              style={{ "--bar-target": `${taskPct}%` } as React.CSSProperties}
            >
              {taskPct > 15 && <span className="font-black text-[10px] text-white">{taskPct}%</span>}
            </div>
          </div>
        </div>
      )}

      {/* ── CTA STATES ── */}

      {/* Needs baseline */}
      {!data.has_baseline && (
        <div className="border-8 border-neo-black bg-neo-accent shadow-neo-xl p-8 space-y-5 -rotate-1 hover:rotate-0 transition-transform duration-200 stagger-5">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 border-4 border-neo-black bg-white flex items-center justify-center font-black text-3xl shadow-neo-sm shrink-0">!</div>
            <div>
              <p className="font-black uppercase tracking-widest text-xs mb-1 text-neo-black/60">Required First Step</p>
              <h2 className="text-3xl font-black uppercase tracking-tighter leading-none">Baseline Needed</h2>
            </div>
          </div>
          <p className="font-bold text-lg">Your therapist needs your baseline assessment before creating your therapy plan.</p>
          <Link href="/patient/baseline">
            <NeoButton size="lg" className="w-full text-lg py-5">START BASELINE NOW →</NeoButton>
          </Link>
        </div>
      )}

      {/* Waiting for plan */}
      {data.has_baseline && !data.has_approved_plan && (
        <div className="border-8 border-neo-black bg-neo-muted shadow-neo-lg p-8 space-y-4 rotate-1 hover:rotate-0 transition-transform duration-200 stagger-5">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 border-4 border-neo-black bg-neo-secondary flex items-center justify-center text-3xl shrink-0">⏳</div>
            <div>
              <p className="font-black uppercase tracking-widest text-xs mb-1 text-neo-black/50">Stand By</p>
              <h2 className="text-3xl font-black uppercase tracking-tighter leading-none">Plan Pending</h2>
            </div>
          </div>
          <p className="font-bold">Baseline complete. Your therapist is preparing your therapy plan — check back soon!</p>
        </div>
      )}

      {/* All tasks done */}
      {data.has_baseline && data.has_approved_plan && allTasksDone && (
        <div className="border-8 border-neo-black bg-neo-secondary shadow-neo-xl p-8 text-center space-y-4 stagger-5">
          <div className="text-6xl animate-pop-in">🎉</div>
          <h2 className="text-4xl font-black uppercase tracking-tighter">All Done Today!</h2>
          <p className="font-bold text-lg">You&apos;ve nailed all of today&apos;s tasks. Check back tomorrow!</p>
        </div>
      )}

      {/* Active plan + tasks */}
      {data.has_baseline && data.has_approved_plan && !allTasksDone && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 stagger-5">

          {/* Plan card */}
          <div className="border-4 border-neo-black bg-white shadow-neo-md hover:-translate-y-1 hover:shadow-neo-lg transition-all duration-200 p-6 space-y-4">
            <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-xs -rotate-1">Current Plan</div>
            <h2 className="text-2xl font-black uppercase tracking-tighter leading-tight">{data.plan_name}</h2>
            <div className="space-y-1 text-sm font-bold">
              <div className="flex items-center gap-2">
                <span className="border-2 border-neo-black bg-neo-secondary px-2 py-0.5 font-black uppercase text-[10px]">From</span>
                <span>{formatPlanDate(data.plan_start_date)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="border-2 border-neo-black bg-neo-secondary px-2 py-0.5 font-black uppercase text-[10px]">To</span>
                <span>{formatPlanDate(data.plan_end_date)}</span>
              </div>
            </div>
            <div className="border-2 border-neo-black bg-neo-accent px-3 py-1 font-black uppercase text-xs tracking-widest inline-block">
              {data.plan_status}
            </div>
          </div>

          {/* Tasks CTA card */}
          <div className="border-4 border-neo-black bg-neo-accent shadow-neo-md hover:translate-x-1 hover:-translate-y-1 hover:shadow-neo-lg transition-all duration-200 p-6 space-y-4 flex flex-col justify-between">
            <div>
              <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-xs rotate-1 mb-3">Action Required</div>
              <h2 className="text-2xl font-black uppercase tracking-tighter leading-tight">Today&apos;s Tasks</h2>
              <div className="text-7xl font-black leading-none mt-3 drop-shadow-[4px_4px_0_rgba(0,0,0,1)]">
                {data.today_tasks}
              </div>
              <p className="font-bold text-sm mt-2 text-neo-black/70">{completedTasks} of {totalTasks} completed</p>
            </div>
            <Link href="/patient/tasks">
              <NeoButton size="lg" className="w-full text-base border-neo-black">GO TO TASKS →</NeoButton>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
