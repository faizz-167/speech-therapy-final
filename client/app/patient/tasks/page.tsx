"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Assignment, HomeSummary } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import Link from "next/link";

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

  if (loading) return <LoadingState label="Loading your tasks..." />;
  if (error) return <ErrorState message={error} />;

  const allCompleted = tasks.length > 0 && tasks.every((t) => t.status === "completed");

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

      {allCompleted ? (
        <EmptyState
          icon="🎉"
          heading="All Done for Today!"
          subtext="You've finished all tasks for today. Great work — check back tomorrow!"
        />
      ) : tasks.length === 0 && !homeSummary?.has_approved_plan ? (
        <EmptyState
          icon="📋"
          heading="No Plan Yet"
          subtext="Your therapist hasn't approved a plan yet. Check back soon."
        />
      ) : tasks.length === 0 ? (
        <EmptyState
          icon="📭"
          heading="No Tasks Today"
          subtext="No tasks are scheduled for today — check back tomorrow."
        />
      ) : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <NeoCard key={t.assignment_id} className="flex items-center justify-between">
              <div>
                <p className="font-black uppercase">{t.task_name}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-gray-500">{t.task_mode}</p>
                  {t.current_level ? (
                    <span className="bg-neo-secondary text-xs font-black uppercase border-2 border-black px-2 py-0.5">
                      {t.current_level}
                    </span>
                  ) : null}
                  <span
                    className={`text-xs font-black uppercase border-2 border-black px-2 py-0.5 ${
                      t.status === "completed" ? "bg-[#FFD93D]" : "bg-white"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>
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
