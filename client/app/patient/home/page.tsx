"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList } from "@/components/ui/Skeletons";
import Link from "next/link";

interface HomeData { has_baseline: boolean; today_tasks: number; plan_status: string | null; }

export default function PatientHomePage() {
  const [data, setData] = useState<HomeData | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/baseline/result").catch(() => null),
      api.get("/patient/tasks").catch(() => []),
    ]).then(([baseline, tasks]) => {
      setData({
        has_baseline: !!baseline,
        today_tasks: Array.isArray(tasks) ? tasks.length : 0,
        plan_status: null,
      });
    });
  }, []);

  if (!data) return <SkeletonList count={2} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">Welcome Back</h1>
      {!data.has_baseline && (
        <NeoCard accent="accent" className="space-y-3">
          <h2 className="font-black uppercase text-lg">Complete Your Baseline Assessment</h2>
          <p className="font-medium">Your therapist needs your baseline scores before creating your therapy plan.</p>
          <Link href="/patient/baseline"><NeoButton>Start Baseline</NeoButton></Link>
        </NeoCard>
      )}
      {data.has_baseline && (
        <NeoCard accent="secondary" className="space-y-3">
          <h2 className="font-black uppercase text-lg">Today&apos;s Tasks</h2>
          <p className="text-2xl font-black">{data.today_tasks} task(s)</p>
          <Link href="/patient/tasks"><NeoButton>Go to Tasks</NeoButton></Link>
        </NeoCard>
      )}
    </div>
  );
}
