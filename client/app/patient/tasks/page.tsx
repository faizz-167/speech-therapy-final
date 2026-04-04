"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Assignment } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";
import Link from "next/link";

interface HomeSummary {
  has_approved_plan: boolean;
  plan_name: string | null;
  plan_start_date: string | null;
  plan_end_date: string | null;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Assignment[]>([]);
  const [homeSummary, setHomeSummary] = useState<HomeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Assignment[]>("/patient/tasks"),
      api.get<HomeSummary>("/patient/home").catch(() => null),
    ])
      .then(([taskList, summary]) => {
        setTasks(taskList);
        setHomeSummary(summary);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonList />;
  if (error) return <ErrorBanner message={error} />;

  const day = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="text-3xl font-black uppercase">Today&apos;s Tasks</h1>
        <p className="font-bold text-gray-600">{day}</p>
      </div>

      {tasks.length === 0 ? (
        <NeoCard>
          <p className="font-bold">No tasks scheduled for today.</p>
          {homeSummary?.has_approved_plan && (
            <p className="mt-2 text-sm font-medium text-gray-600">
              Your current plan, {homeSummary.plan_name}, runs from {homeSummary.plan_start_date} to {homeSummary.plan_end_date}.
            </p>
          )}
        </NeoCard>
      ) : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <NeoCard key={t.assignment_id} className="flex items-center justify-between">
              <div>
                <p className="font-black uppercase">{t.task_name}</p>
                <p className="text-sm font-medium text-gray-500">{t.task_mode}</p>
                <span
                  className={`text-xs font-black uppercase border-2 border-black px-2 py-0.5 ${
                    t.status === "completed" ? "bg-[#FFD93D]" : "bg-white"
                  }`}
                >
                  {t.status}
                </span>
              </div>
              {t.status !== "completed" && (
                <Link href={`/patient/tasks/${t.assignment_id}`}>
                  <NeoButton>Start</NeoButton>
                </Link>
              )}
            </NeoCard>
          ))}
        </div>
      )}
    </div>
  );
}
