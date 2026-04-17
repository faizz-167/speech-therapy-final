"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { AdaptationActivity, AdaptationEvent, RegeneratedPlan } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function LevelBadge({ level }: { level: string | null }) {
  const l = (level ?? "beginner").toLowerCase();
  const styles: Record<string, string> = {
    beginner: "bg-neo-secondary border-neo-black text-neo-black",
    intermediate: "bg-neo-muted border-neo-black text-neo-black",
    advanced: "bg-neo-accent border-neo-black text-neo-black",
  };
  return (
    <span className={`border-2 px-2 py-0.5 text-[10px] font-black uppercase ${styles[l] ?? "bg-white border-neo-black"}`}>
      {l}
    </span>
  );
}

type PlanStatus = "approved" | "draft" | "archived" | string;

function PlanStatusBadge({ status }: { status: PlanStatus }) {
  const configs: Record<string, { accent: string; icon: string; label: string }> = {
    approved: { accent: "bg-neo-secondary border-neo-black", icon: "✓", label: "Therapist Approved" },
    archived: { accent: "bg-white border-neo-black opacity-60", icon: "⊘", label: "Superseded" },
    draft: { accent: "bg-neo-muted border-neo-black", icon: "⏳", label: "Pending Approval" },
  };
  const c = configs[status] ?? configs.draft;
  return (
    <span className={`border-2 px-2 py-1 font-black uppercase text-[10px] tracking-widest ${c.accent}`}>
      {c.icon} {c.label}
    </span>
  );
}

function RegeneratedPlanPanel({ plan, patientId, onApprove, onReject, busy }: {
  plan: RegeneratedPlan; patientId: string;
  onApprove: (planId: string) => void; onReject: (planId: string) => void; busy: boolean;
}) {
  const [showTasks, setShowTasks] = useState(false);
  const isArchived = plan.status === "archived";
  const isDraft = plan.status === "draft";

  return (
    <div className={`border-4 mt-3 ${isArchived ? "border-neo-black/30 opacity-70" : "border-neo-black"} bg-white`}>
      <div className={`border-b-4 ${isArchived ? "border-neo-black/20 bg-neo-bg" : "border-neo-black bg-neo-muted/30"} px-4 py-3 flex flex-wrap items-center justify-between gap-3`}>
        <div>
          <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/40 mb-0.5">Regenerated Plan</p>
          <h3 className={`font-black uppercase text-sm ${isArchived ? "line-through text-neo-black/40" : ""}`}>{plan.plan_name}</h3>
          <p className="text-[10px] font-medium text-neo-black/40">{new Date(plan.created_at).toLocaleString()}</p>
        </div>
        <PlanStatusBadge status={plan.status} />
      </div>

      {isDraft && (
        <div className="border-b-2 border-neo-muted px-4 py-2 bg-neo-muted/20">
          <p className="text-xs font-bold">⏳ Awaiting your approval. Patient is locked until you approve or reject.</p>
        </div>
      )}
      {plan.status === "approved" && (
        <div className="border-b-2 border-neo-secondary/60 px-4 py-2 bg-neo-secondary/20">
          <p className="text-xs font-bold text-green-800">✓ Active — patient is working on these tasks.</p>
        </div>
      )}
      {isArchived && (
        <div className="border-b-2 border-neo-black/20 px-4 py-2 bg-neo-bg">
          <p className="text-xs font-bold text-neo-black/50">⊘ Replaced when patient escalated again.</p>
        </div>
      )}

      {plan.regeneration_note && (
        <div className="border-b-2 border-neo-black/10 px-4 py-2">
          <p className="text-xs font-medium text-neo-black/50 italic">Engine: {plan.regeneration_note}</p>
        </div>
      )}

      <div className="px-4 py-3 space-y-3">
        <div className="flex flex-wrap gap-2 items-center">
          <button
            onClick={() => setShowTasks((v) => !v)}
            className="border-2 border-neo-black bg-white px-3 py-1.5 font-black uppercase text-[10px] tracking-widest hover:bg-neo-secondary transition-colors"
          >
            {showTasks ? "Hide" : "View"} Tasks ({plan.assignments.length})
          </button>
          {!isArchived && (
            <Link href={`/therapist/patients/${patientId}/plan`}>
              <button className="border-2 border-neo-black bg-white px-3 py-1.5 font-black uppercase text-[10px] tracking-widest hover:bg-neo-muted transition-colors">
                Open Plan Editor →
              </button>
            </Link>
          )}
        </div>

        {isDraft && (
          <div className="flex gap-2">
            <NeoButton className="text-xs h-9 px-3" disabled={busy} onClick={() => onApprove(plan.plan_id)}>Approve Plan</NeoButton>
            <NeoButton variant="secondary" className="text-xs h-9 px-3" disabled={busy} onClick={() => onReject(plan.plan_id)}>Reject</NeoButton>
          </div>
        )}

        {showTasks && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            {plan.assignments.map((a) => (
              <div key={a.assignment_id} className={`flex items-center justify-between border-2 px-3 py-2 ${isArchived ? "border-neo-black/15 bg-neo-bg opacity-50" : "border-neo-black/20 bg-neo-muted/15"}`}>
                <span className={`text-xs font-bold truncate mr-2 ${isArchived ? "text-neo-black/50" : ""}`}>{a.task_name}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <LevelBadge level={a.initial_level_name} />
                  {a.day_index !== null && (
                    <span className="text-[10px] font-bold text-neo-black/40 w-7 text-right">{DAY_LABELS[a.day_index] ?? `D${a.day_index}`}</span>
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

function AdaptationEventCard({ event, patientId, onApprove, onReject, busy, index }: {
  event: AdaptationEvent; patientId: string;
  onApprove: (planId: string) => void; onReject: (planId: string) => void; busy: boolean; index: number;
}) {
  const [showLevelChanges, setShowLevelChanges] = useState(false);
  const isEscalated = event.escalated || event.adaptation_count >= 2;

  return (
    <div className={`border-4 border-neo-black bg-white shadow-neo-sm stagger-${Math.min(index + 1, 6)}`}>
      {/* Timeline connector */}
      <div className={`border-b-4 border-neo-black px-5 py-3 flex flex-wrap items-center gap-3 ${isEscalated ? "bg-neo-accent" : "bg-neo-secondary"}`}>
        <div className="w-8 h-8 border-4 border-neo-black bg-white flex items-center justify-center font-black text-sm shadow-neo-sm shrink-0">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-black uppercase text-sm">{event.task_name}</span>
            {isEscalated && (
              <span className="border-2 border-neo-black bg-neo-black text-white px-2 py-0.5 text-[10px] font-black uppercase tracking-widest">
                ESCALATED
              </span>
            )}
          </div>
          <p className="text-[10px] font-medium text-neo-black/50">{new Date(event.session_date).toLocaleDateString()}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="p-5 space-y-4">
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Adaptation Count", value: event.adaptation_count },
            { label: "Fails / Trigger", value: 3 },
            { label: "Status", value: isEscalated ? "Escalated" : "Adapted" },
          ].map(({ label, value }) => (
            <div key={label} className="border-2 border-neo-black px-3 py-2 text-center bg-neo-bg">
              <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">{label}</p>
              <p className="font-black text-xl">{value}</p>
            </div>
          ))}
        </div>

        {/* Level change history */}
        {event.adaptation_history.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setShowLevelChanges((v) => !v)}
              className="border-2 border-neo-black bg-white px-3 py-1.5 font-black uppercase text-[10px] tracking-widest hover:bg-neo-secondary transition-colors"
            >
              {showLevelChanges ? "Hide" : "Show"} Level Changes ({event.adaptation_history.length})
            </button>
            {showLevelChanges && (
              <div className="space-y-2">
                {event.adaptation_history.map((step, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 border-2 border-neo-black/15 px-3 py-2 bg-neo-muted/20 text-xs">
                    <span className="font-black uppercase text-neo-black/40 text-[10px] w-12 shrink-0">Step {i + 1}</span>
                    <LevelBadge level={step.from_level} />
                    <span className="font-black text-neo-black/40">→</span>
                    <LevelBadge level={step.to_level} />
                    <span className="text-[10px] font-medium text-neo-black/50 ml-auto">
                      score <strong>{step.final_score.toFixed(1)}</strong> · {step.reason.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Linked regenerated plan */}
        {isEscalated && event.linked_plan && (
          <RegeneratedPlanPanel
            plan={event.linked_plan}
            patientId={patientId}
            onApprove={onApprove}
            onReject={onReject}
            busy={busy}
          />
        )}
        {isEscalated && !event.linked_plan && (
          <div className="border-4 border-neo-muted bg-neo-muted/20 px-4 py-3 text-xs font-bold">
            ⚠ Plan regeneration triggered. Check the{" "}
            <Link href={`/therapist/patients/${patientId}/plan`} className="underline font-black">Plan Editor</Link>{" "}
            for the latest draft.
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdaptationsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const approveMutation = useMutation({
    mutationFn: (planId: string) => api.post(`/plans/${planId}/approve`, {}),
    onSuccess: async () => {
      toast.success("Plan approved.");
      await qc.invalidateQueries({ queryKey: ["therapist", "adaptation-activity", id] });
      await qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
    },
    onError: (error: unknown) => toast.error(error instanceof Error ? error.message : "Approval failed"),
  });

  const rejectMutation = useMutation({
    mutationFn: (planId: string) => api.post(`/plans/${planId}/reject`, {}),
    onSuccess: async () => {
      toast.success("Plan rejected.");
      await qc.invalidateQueries({ queryKey: ["therapist", "adaptation-activity", id] });
      await qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
    },
    onError: (error: unknown) => toast.error(error instanceof Error ? error.message : "Rejection failed"),
  });

  const { data, isLoading, error } = useQuery<AdaptationActivity>({
    queryKey: ["therapist", "adaptation-activity", id],
    queryFn: () => api.get<AdaptationActivity>(`/therapist/patients/${id}/adaptation-activity`),
  });

  if (isLoading) return <LoadingState label="Loading adaptation history..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load adaptation data"} />;

  const hasEvents = (data?.adaptation_events.length ?? 0) > 0;
  const escalatedCount = data?.adaptation_events.filter((e) => e.escalated || e.adaptation_count >= 2).length ?? 0;

  return (
    <div className="animate-fade-up p-4 md:p-6 max-w-4xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="flex items-center gap-4 border-b-8 border-neo-black pb-6">
        <Link href={`/therapist/patients/${id}`} className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-xs tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-0.5 active:translate-y-0.5 active:shadow-none shrink-0">
          ← Back
        </Link>
        <div>
          <div className="inline-block bg-neo-accent border-4 border-neo-black px-3 py-0.5 font-black uppercase tracking-widest text-xs mb-1 -rotate-1 shadow-neo-sm">Timeline</div>
          <h1 className="text-4xl font-black uppercase tracking-tighter leading-none">Adaptation History</h1>
        </div>
      </div>

      {/* ── EXPLAINER ── */}
      <div className="border-4 border-neo-black bg-neo-muted/30 px-5 py-4 space-y-1 stagger-1">
        <p className="font-black uppercase text-xs tracking-widest mb-2">How Adaptations Work</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-medium">
          <div className="flex items-start gap-2 border-2 border-neo-black px-3 py-2 bg-white">
            <span className="font-black text-lg shrink-0">①</span>
            <span><strong>Adaptation 1:</strong> After 3 consecutive fails, task drops one level.</span>
          </div>
          <div className="flex items-start gap-2 border-2 border-neo-black px-3 py-2 bg-neo-accent">
            <span className="font-black text-lg shrink-0">②</span>
            <span><strong>Escalation:</strong> If it fails again, a new plan is auto-generated for your review.</span>
          </div>
        </div>
      </div>

      {/* ── SUMMARY STATS ── */}
      {hasEvents && (
        <div className="grid grid-cols-2 gap-4 stagger-2">
          <div className="border-4 border-neo-black bg-neo-secondary shadow-neo-sm p-4 text-center">
            <div className="text-4xl font-black">{data!.adaptation_events.length}</div>
            <div className="font-black uppercase text-xs tracking-widest mt-2">Total Events</div>
          </div>
          <div className="border-4 border-neo-black bg-neo-accent shadow-neo-sm p-4 text-center">
            <div className="text-4xl font-black">{escalatedCount}</div>
            <div className="font-black uppercase text-xs tracking-widest mt-2">Escalations</div>
          </div>
        </div>
      )}

      {/* ── EVENTS ── */}
      {!hasEvents ? (
        <EmptyState icon="📊" heading="No Adaptation Events" subtext="No adaptation activity has been recorded for this patient yet." />
      ) : (
        <div className="space-y-4">
          {data!.adaptation_events.map((event, i) => (
            <AdaptationEventCard
              key={event.session_id}
              event={event}
              patientId={id}
              onApprove={(planId) => approveMutation.mutate(planId)}
              onReject={(planId) => rejectMutation.mutate(planId)}
              busy={approveMutation.isPending || rejectMutation.isPending}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  );
}
