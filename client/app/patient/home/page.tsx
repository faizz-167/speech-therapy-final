"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import Link from "next/link";
import { Assignment, BaselineResult, HomeData, PatientProfile } from "@/types";

type HomeBundle = {
  home: HomeData;
  profile: PatientProfile | null;
  tasks: Assignment[];
  baseline: BaselineResult | null;
};

function formatPlanDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "—"
    : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function PatientHomePage() {
  const [bundle, setBundle] = useState<HomeBundle | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<HomeData>("/patient/home"),
      api.get<PatientProfile>("/patient/profile").catch(() => null),
      api.get<Assignment[]>("/patient/tasks").catch(() => []),
      api.get<BaselineResult | null>("/baseline/result").catch(() => null),
    ])
      .then(([home, profile, tasks, baseline]) => setBundle({ home, profile, tasks, baseline }))
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!bundle) return <LoadingState label="Loading your home screen..." />;

  const { home: data, profile, tasks, baseline } = bundle;
  const allTasksDone =
    data.has_approved_plan &&
    tasks.length > 0 &&
    tasks.every((t) => t.status === "completed");

  return (
    <div className="space-y-10 animate-fade-up max-w-4xl mx-auto p-4 md:p-8">
      <div className="relative inline-block mb-6 mt-4">
        <h1 className="text-5xl md:text-6xl font-black uppercase tracking-tighter relative z-10 text-white text-stroke-black drop-shadow-[4px_4px_0_rgba(0,0,0,1)]">
          Welcome Back{data.full_name && `, ${data.full_name}`}
        </h1>
        <div className="absolute top-3 left-3 w-full h-full bg-neo-secondary border-4 border-neo-black z-0"></div>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <NeoCard accent="secondary" className="text-center py-4">
          <div className="text-3xl font-black">
            {profile?.current_streak ?? "—"}
          </div>
          <div className="text-xs font-black uppercase tracking-widest pt-1">
            🔥 Current Streak
          </div>
        </NeoCard>
        <NeoCard accent="default" className="text-center py-4">
          <div className="text-3xl font-black">{data.today_tasks}</div>
          <div className="text-xs font-black uppercase tracking-widest pt-1">
            📋 Tasks Today
          </div>
        </NeoCard>
        <NeoCard accent="muted" className="text-center py-4">
          <div className="text-3xl font-black">{baseline?.level ? baseline.level.toUpperCase() : "—"}</div>
          <div className="text-xs font-black uppercase tracking-widest pt-1">
            🧭 Baseline Level
          </div>
        </NeoCard>
      </div>

      {/* CTA waterfall */}
      {!data.has_baseline && (
        <NeoCard accent="accent" className="space-y-5 transform -rotate-1 relative z-10 hover:rotate-0 transition-transform p-8 border-8">
          <div className="flex items-center gap-4 border-b-8 border-neo-black pb-6 mb-6">
            <div className="min-w-16 w-16 h-16 bg-white border-4 border-neo-black flex items-center justify-center font-black text-4xl shadow-neo-sm shadow-neo-black">!</div>
            <h2 className="font-black uppercase text-4xl tracking-tighter leading-none">Baseline<br/>Needed</h2>
          </div>
          <p className="font-bold text-2xl leading-snug">Your therapist needs your baseline scores before creating your therapy plan.</p>
          <Link href="/patient/baseline" className="inline-block w-full pt-6">
            <NeoButton size="lg" className="w-full text-2xl py-8 tracking-widest border-4">START BASELINE NOW</NeoButton>
          </Link>
        </NeoCard>
      )}

      {data.has_baseline && !data.has_approved_plan && (
        <div className="relative mt-12">
          <div className="absolute -top-6 -right-6 w-24 h-24 bg-neo-warning border-4 border-neo-black rounded-none flex items-center justify-center rotate-[15deg] z-20 shadow-neo-sm">
             <span className="font-black text-2xl text-center leading-none uppercase">Wait<br/>ing</span>
          </div>
          <NeoCard accent="muted" className="space-y-4 transform rotate-1 p-8 border-8">
            <h2 className="font-black uppercase text-4xl tracking-tighter">Plan Pending</h2>
            <p className="font-bold text-xl">Your baseline is complete. Your therapist has not approved a therapy plan yet.</p>
          </NeoCard>
        </div>
      )}

      {data.has_baseline && data.has_approved_plan && allTasksDone && (
        <NeoCard accent="secondary" className="space-y-5 p-8 border-8 text-center">
          <div className="text-6xl">🎉</div>
          <h2 className="font-black uppercase text-4xl tracking-tighter">All Done Today!</h2>
          <p className="font-bold text-xl">You&apos;ve completed all of today&apos;s tasks. Great work — check back tomorrow!</p>
        </NeoCard>
      )}

      {data.has_baseline && data.has_approved_plan && !allTasksDone && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
          <NeoCard accent="default" className="space-y-5 hover:-translate-y-2 transition-transform p-8 shadow-neo-lg">
            <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-sm mb-2 -rotate-2">Current Plan</div>
            <h2 className="font-black uppercase text-4xl tracking-tighter leading-none">{data.plan_name}</h2>
            <div className="font-bold border-t-8 border-neo-black pt-5 mt-4 text-lg">
              <span className="bg-neo-secondary px-2 border-2 border-neo-black inline-block mb-1">FROM</span> {formatPlanDate(data.plan_start_date)} <br/>
              <span className="bg-neo-secondary px-2 border-2 border-neo-black inline-block mt-3 mb-1">TO</span> {formatPlanDate(data.plan_end_date)}
            </div>
            <div className="mt-6 inline-block px-4 py-2 bg-neo-accent border-4 border-neo-black font-black uppercase tracking-widest text-lg shadow-neo-sm">{data.plan_status}</div>
          </NeoCard>

          <NeoCard accent="secondary" className="space-y-4 flex flex-col justify-between hover:translate-x-2 transition-transform p-8 shadow-neo-lg">
            <div>
               <div className="inline-block bg-neo-black text-white px-3 py-1 font-black uppercase tracking-widest text-sm mb-4 rotate-2">Action Required</div>
               <h2 className="font-black uppercase text-4xl tracking-tighter">Today&apos;s Tasks</h2>
               <div className="text-8xl font-black mt-6 drop-shadow-[6px_6px_0_rgba(0,0,0,1)] text-white text-stroke-black my-4">{data.today_tasks}</div>
            </div>
            <Link href="/patient/tasks" className="block w-full mt-8">
              <NeoButton size="lg" className="w-full text-2xl py-8 border-4 border-neo-black transition-colors">GO TO TASKS ➔</NeoButton>
            </Link>
          </NeoCard>
        </div>
      )}
    </div>
  );
}
