"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  AdaptationActivity,
  AdaptationEvent,
  RegeneratedPlan,
} from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const LEVEL_COLORS: Record<string, string> = {
  beginner: "bg-green-100 border-green-600 text-green-800",
  intermediate: "bg-yellow-100 border-yellow-600 text-yellow-800",
  advanced: "bg-red-100 border-red-600 text-red-800",
};

function LevelBadge({ level }: { level: string | null }) {
  const l = (level ?? "beginner").toLowerCase();
  const cls = LEVEL_COLORS[l] ?? "bg-gray-100 border-gray-400 text-gray-700";
  return (
    <span className={`border-2 px-2 py-0.5 text-xs font-black uppercase ${cls}`}>
      {l}
    </span>
  );
}

type PlanStatus = "approved" | "draft" | "archived" | string;

function PlanStatusBadge({ status }: { status: PlanStatus }) {
  if (status === "approved") {
    return (
      <span className="border-4 border-green-700 bg-green-100 text-green-800 px-3 py-2 font-black uppercase text-xs tracking-widest">
        ✓ Therapist Approved
      </span>
    );
  }
  if (status === "archived") {
    return (
      <span className="border-4 border-gray-500 bg-gray-100 text-gray-600 px-3 py-2 font-black uppercase text-xs tracking-widest">
        ⊘ Superseded
      </span>
    );
  }
  // draft or unknown
  return (
    <span className="border-4 border-orange-500 bg-orange-100 text-orange-700 px-3 py-2 font-black uppercase text-xs tracking-widest">
      ⏳ Pending Approval
    </span>
  );
}

function RegeneratedPlanPanel({
  plan,
  patientId,
}: {
  plan: RegeneratedPlan;
  patientId: string;
}) {
  const [showTasks, setShowTasks] = useState(false);
  const isArchived = plan.status === "archived";
  const isDraft = plan.status === "draft";

  return (
    <div className={`border-4 bg-white mt-3 ${isArchived ? "border-gray-400 opacity-80" : "border-neo-black"}`}>
      {/* Header bar */}
      <div className={`flex flex-wrap items-center justify-between gap-3 border-b-4 px-4 py-3 ${isArchived ? "border-gray-300 bg-gray-50" : "border-neo-black bg-neo-muted/30"}`}>
        <div>
          <p className="text-xs font-black uppercase tracking-widest mb-0.5 text-neo-black/50">
            Regenerated Plan
          </p>
          <h3 className={`font-black uppercase text-base ${isArchived ? "line-through text-gray-500" : ""}`}>
            {plan.plan_name}
          </h3>
          <p className="text-xs font-medium text-neo-black/50 mt-0.5">
            Created {new Date(plan.created_at).toLocaleString()}
          </p>
        </div>
        <PlanStatusBadge status={plan.status} />
      </div>

      {/* Status-specific contextual notes */}
      {isArchived && (
        <div className="border-b-2 border-gray-300 px-4 py-2 bg-gray-50">
          <p className="text-xs font-bold text-gray-600">
            ⊘ This plan was stopped and replaced when the patient escalated again. It is no longer active.
          </p>
        </div>
      )}
      {isDraft && (
        <div className="border-b-2 border-orange-300 px-4 py-2 bg-orange-50">
          <p className="text-xs font-bold text-orange-700">
            ⏳ This plan is awaiting your approval. The patient cannot proceed until you approve it in the Plan Editor.
          </p>
        </div>
      )}
      {plan.status === "approved" && (
        <div className="border-b-2 border-green-300 px-4 py-2 bg-green-50">
          <p className="text-xs font-bold text-green-700">
            ✓ You approved this plan. The patient is currently working on these tasks.
          </p>
        </div>
      )}

      {/* Regeneration engine note */}
      {plan.regeneration_note && (
        <div className="border-b-2 border-neo-black/10 px-4 py-2">
          <p className="text-xs font-medium text-neo-black/60 italic">
            Engine note: {plan.regeneration_note}
          </p>
        </div>
      )}

      {/* Task list */}
      <div className="px-4 py-3 space-y-3">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setShowTasks((v) => !v)}
            className="font-black uppercase tracking-widest text-xs border-2 border-neo-black px-3 py-1.5 bg-white hover:bg-neo-secondary transition-colors"
          >
            {showTasks ? "Hide" : "View"} Plan Tasks ({plan.assignments.length})
          </button>
          {!isArchived && (
            <Link href={`/therapist/patients/${patientId}/plan`}>
              <NeoButton variant="ghost" className="text-xs py-1.5">
                Open Plan Editor →
              </NeoButton>
            </Link>
          )}
        </div>

        {showTasks && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {plan.assignments.map((a) => (
              <div
                key={a.assignment_id}
                className={`flex items-center justify-between border-2 px-3 py-2 ${
                  isArchived
                    ? "border-gray-200 bg-gray-50 opacity-60"
                    : "border-neo-black/20 bg-neo-muted/20"
                }`}
              >
                <span className={`text-sm font-bold truncate mr-2 ${isArchived ? "text-gray-500" : ""}`}>
                  {a.task_name}
                </span>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <LevelBadge level={a.initial_level_name} />
                  {a.day_index !== null && (
                    <span className="text-xs font-medium text-neo-black/40 w-8 text-right">
                      {DAY_LABELS[a.day_index] ?? `D${a.day_index}`}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AdaptationEventCard({
  event,
  patientId,
}: {
  event: AdaptationEvent;
  patientId: string;
}) {
  const [showLevelChanges, setShowLevelChanges] = useState(false);
  // Treat as escalated when count>=2 regardless of the boolean flag,
  // since older sessions may have adaptive_interventions=2 without the
  // "escalated" key set in their session_notes JSON.
  const isEscalated = event.escalated || event.adaptation_count >= 2;

  return (
    <NeoCard className="space-y-3">
      {/* Task name + badges */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="border-4 border-neo-black px-3 py-1 font-black uppercase text-sm bg-neo-accent">
          {event.task_name}
        </span>
        {isEscalated && (
          <span className="border-2 border-red-700 bg-red-100 px-3 py-1 text-xs font-black uppercase text-red-700">
            ESCALATED — Plan Regenerated
          </span>
        )}
      </div>

      {/* Stat boxes */}
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="border-2 border-neo-black px-3 py-2">
          <p className="text-xs font-black uppercase text-neo-black/50">Adaptation Count</p>
          <p className="font-black text-2xl">{event.adaptation_count}</p>
        </div>
        <div className="border-2 border-neo-black px-3 py-2">
          <p className="text-xs font-black uppercase text-neo-black/50">Failed Attempts / Trigger</p>
          <p className="font-black text-2xl">3</p>
        </div>
        <div className="border-2 border-neo-black px-3 py-2">
          <p className="text-xs font-black uppercase text-neo-black/50">Date</p>
          <p className="font-bold text-sm leading-tight">
            {new Date(event.session_date).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Level change history */}
      {event.adaptation_history.length > 0 && (
        <div>
          <button
            onClick={() => setShowLevelChanges((v) => !v)}
            className="font-black uppercase tracking-widest text-xs border-2 border-neo-black px-3 py-1.5 bg-white hover:bg-neo-secondary transition-colors"
          >
            {showLevelChanges ? "Hide" : "Show"} Level Changes ({event.adaptation_history.length})
          </button>
          {showLevelChanges && (
            <div className="mt-2 space-y-1.5">
              {event.adaptation_history.map((step, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 border-2 border-neo-black/20 px-3 py-2 bg-neo-muted/30 text-sm"
                >
                  <span className="font-black text-xs uppercase text-neo-black/50">
                    Step {i + 1}
                  </span>
                  <LevelBadge level={step.from_level} />
                  <span className="font-black text-neo-black/60">→</span>
                  <LevelBadge level={step.to_level} />
                  <span className="text-xs font-medium text-neo-black/60 ml-auto">
                    score <strong>{step.final_score.toFixed(1)}</strong>
                    &nbsp;·&nbsp;
                    {step.reason.replace(/_/g, " ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Inline regenerated plan panel — shown when escalated and plan is linked */}
      {isEscalated && event.linked_plan && (
        <RegeneratedPlanPanel plan={event.linked_plan} patientId={patientId} />
      )}

      {/* Escalated but no linked plan found — warn therapist */}
      {isEscalated && !event.linked_plan && (
        <div className="border-2 border-orange-400 bg-orange-50 px-4 py-3 text-sm font-medium text-orange-700">
          ⚠ A plan regeneration was triggered for this escalation. It may still be processing, or check the{" "}
          <Link href={`/therapist/patients/${patientId}/plan`} className="underline font-black">
            Plan Editor
          </Link>{" "}
          for the latest draft.
        </div>
      )}
    </NeoCard>
  );
}

export default function AdaptationsPage() {
  const { id } = useParams<{ id: string }>();

  const { data, isLoading, error } = useQuery<AdaptationActivity>({
    queryKey: ["therapist", "adaptation-activity", id],
    queryFn: () =>
      api.get<AdaptationActivity>(`/therapist/patients/${id}/adaptation-activity`),
  });

  if (isLoading) return <LoadingState label="Loading adaptation history..." />;
  if (error)
    return (
      <ErrorState
        message={
          error instanceof Error ? error.message : "Failed to load adaptation data"
        }
      />
    );

  const hasEvents = (data?.adaptation_events.length ?? 0) > 0;

  return (
    <div className="space-y-6 animate-fade-up pt-4">
      <div className="flex items-center gap-4 mb-2">
        <Link
          href={`/therapist/patients/${id}`}
          className="font-black uppercase tracking-widest text-sm border-4 border-neo-black px-4 py-2 bg-white hover:bg-neo-secondary transition-colors shadow-neo-sm"
        >
          ← BACK
        </Link>
        <h1 className="font-black text-3xl uppercase tracking-tighter">
          Adaptation History
        </h1>
      </div>

      <div className="bg-neo-primary/30 border-4 border-neo-black px-4 py-3 text-sm font-medium -rotate-0.5">
        <strong>How adaptations work:</strong> After 3 consecutive failed attempts, the task drops one level (Adaptation 1).
        If it fails again at the new level, the task is escalated (Adaptation 2) and a new plan is auto-generated for therapist review.
      </div>

      {!hasEvents ? (
        <EmptyState
          icon="📊"
          heading="No Adaptation Events"
          subtext="No adaptation activity has been recorded for this patient yet."
        />
      ) : (
        <div className="space-y-4">
          {data!.adaptation_events.map((event) => (
            <AdaptationEventCard key={event.session_id} event={event} patientId={id} />
          ))}
        </div>
      )}
    </div>
  );
}
