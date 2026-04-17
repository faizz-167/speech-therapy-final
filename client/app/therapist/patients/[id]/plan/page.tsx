"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Plan, Task, Assignment, PlanRevisionEntry } from "@/types";
import { KanbanBoard } from "@/components/therapist/KanbanBoard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import Link from "next/link";

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [showHistory, setShowHistory] = useState(false);
  const [generating, setGenerating] = useState(false);

  const { data: plan, error, isLoading, refetch: refetchPlan } = useQuery<Plan | null>({
    queryKey: ["therapist", "plan", id],
    queryFn: () => api.get<Plan | null>(`/plans/patient/${id}/current`),
  });

  const { data: availableTasks = [] } = useQuery<Task[]>({
    queryKey: ["therapist", "plan-tasks", plan?.plan_id],
    queryFn: () => api.get<Task[]>(`/plans/${plan!.plan_id}/tasks-for-defects`),
    enabled: !!plan?.plan_id,
  });

  const { data: revisionHistory = [] } = useQuery<PlanRevisionEntry[]>({
    queryKey: ["therapist", "plan-revisions", plan?.plan_id],
    queryFn: () => api.get<PlanRevisionEntry[]>(`/plans/${plan!.plan_id}/revision-history`).catch(() => [] as PlanRevisionEntry[]),
    enabled: !!plan?.plan_id,
  });

  const moveMutation = useMutation({
    mutationFn: ({ assignmentId, newDayIndex }: { assignmentId: string; newDayIndex: number }) =>
      api.patch(`/plans/${plan!.plan_id}/tasks/${assignmentId}`, { day_index: newDayIndex }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["therapist", "plan", id] }); qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] }); toast.success("Task moved."); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Move failed"),
  });

  const addMutation = useMutation({
    mutationFn: ({ taskId, dayIndex }: { taskId: string; dayIndex: number }) =>
      api.post<Assignment>(`/plans/${plan!.plan_id}/tasks`, { task_id: taskId, day_index: dayIndex }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["therapist", "plan", id] }); qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] }); toast.success("Task added."); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Add failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (assignmentId: string) => api.delete(`/plans/${plan!.plan_id}/tasks/${assignmentId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["therapist", "plan", id] }); qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] }); toast.success("Task removed."); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Delete failed"),
  });

  const updateLevelMutation = useMutation({
    mutationFn: ({ assignmentId, levelName }: { assignmentId: string; levelName: string }) =>
      api.patch<Assignment>(`/plans/${plan!.plan_id}/tasks/${assignmentId}`, { initial_level_name: levelName }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["therapist", "plan", id] }); qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] }); toast.success("Task level updated."); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Level update failed"),
  });

  const approveMutation = useMutation({
    mutationFn: () => api.post(`/plans/${plan!.plan_id}/approve`, {}),
    onSuccess: () => { toast.success("Plan approved and visible to patient."); qc.invalidateQueries({ queryKey: ["therapist", "plan", id] }); qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] }); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Approval failed"),
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/plans/${plan!.plan_id}/reject`, {}),
    onSuccess: async () => {
      toast.success("Plan rejected.");
      await qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
      await qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] });
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Rejection failed"),
  });

  async function handleGenerate() {
    setGenerating(true);
    try {
      const baseline = await api.get<{ level: string } | null>(`/baseline/therapist-view/${id}`);
      const level = (baseline as { level?: string } | null)?.level ?? "easy";
      await api.post<Plan>("/plans/generate", { patient_id: id, baseline_level: level });
      await refetchPlan();
      toast.success("New plan generated.");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  const isMutating = moveMutation.isPending || addMutation.isPending || deleteMutation.isPending || updateLevelMutation.isPending;

  if (isLoading) return <LoadingState label="Loading plan..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  return (
    <div className="animate-fade-up p-4 md:p-6 max-w-7xl mx-auto space-y-6">

      {/* ── HEADER ── */}
      <div className="flex items-center gap-4 border-b-8 border-neo-black pb-6">
        <Link href={`/therapist/patients/${id}`} className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-xs tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-0.5 active:translate-y-0.5 active:shadow-none shrink-0">
          ← Back
        </Link>
        <div>
          <div className="inline-block bg-neo-accent border-4 border-neo-black px-3 py-0.5 font-black uppercase tracking-widest text-xs mb-1 rotate-1 shadow-neo-sm">Plan Editor</div>
          <h1 className="text-4xl font-black uppercase tracking-tighter leading-none">Therapy Plan</h1>
        </div>
      </div>

      {!plan ? (
        <EmptyState
          icon="📝"
          heading="No Plan Yet"
          subtext="Generate a weekly progression framework for this patient."
          cta={{ label: generating ? "Generating…" : "Generate New Plan", onClick: handleGenerate }}
        />
      ) : (
        <div className="space-y-6">
          {/* ── PLAN META CARD ── */}
          <div className="border-4 border-neo-black bg-white shadow-neo-md overflow-hidden">
            <div className={`border-b-4 border-neo-black px-6 py-4 ${plan.status === "approved" ? "bg-neo-secondary" : "bg-neo-muted"}`}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black uppercase tracking-tighter">{plan.plan_name || `Week of ${plan.start_date ?? "TBD"}`}</h2>
                  <p className="font-bold text-sm text-neo-black/60 mt-0.5">{plan.start_date ?? "TBD"} — {plan.end_date ?? "TBD"}</p>
                  {plan.goals && !plan.goals.includes("auto-generated after escalation") && (
                    <p className="text-sm font-medium mt-2 text-neo-black/70 max-w-lg">{plan.goals}</p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {isMutating && (
                    <span className="border-2 border-neo-black/30 px-3 py-1 text-xs font-bold uppercase tracking-widest text-neo-black/50">Saving…</span>
                  )}
                  {plan.status === "approved" && (
                    <span className="border-4 border-neo-black bg-neo-black text-white px-4 py-2 font-black uppercase text-xs tracking-widest">✓ Approved</span>
                  )}
                  {plan.status === "draft" && (
                    <>
                      <NeoButton onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending || rejectMutation.isPending}>
                        {approveMutation.isPending ? "Approving…" : "✓ Approve Plan"}
                      </NeoButton>
                      <NeoButton variant="secondary" onClick={() => rejectMutation.mutate()} disabled={approveMutation.isPending || rejectMutation.isPending}>
                        {rejectMutation.isPending ? "Rejecting…" : "Reject"}
                      </NeoButton>
                    </>
                  )}
                  <NeoButton variant="ghost" onClick={handleGenerate} disabled={generating}>
                    {generating ? "Generating…" : "🔄 Regenerate"}
                  </NeoButton>
                </div>
              </div>
            </div>

            {/* Escalation alert */}
            {plan.goals?.includes("auto-generated after escalation") && (
              <div className="border-b-4 border-neo-black bg-neo-accent px-6 py-3">
                <p className="font-black uppercase text-xs tracking-widest mb-0.5">Auto-Regenerated After Escalation</p>
                <p className="font-bold text-sm">{plan.goals}</p>
                <p className="text-xs font-medium mt-1 text-neo-black/70">All tasks set to new level. Approve this plan to unblock the patient.</p>
              </div>
            )}

            {/* Status info bar */}
            <div className="px-6 py-3 bg-neo-bg border-b-0 text-sm font-medium text-neo-black/60">
              {plan.status === "approved"
                ? "You are editing the patient-visible approved plan. Changes appear on the patient side after refresh."
                : "Draft plan — patient keeps seeing their last approved plan until you approve this one."}
            </div>
          </div>

          {/* ── KANBAN ── */}
          <KanbanBoard
            assignments={plan.assignments}
            availableTasks={availableTasks}
            onMove={(assignmentId, newDayIndex) => moveMutation.mutateAsync({ assignmentId, newDayIndex }).then(() => undefined)}
            onAdd={(taskId, dayIndex) => addMutation.mutateAsync({ taskId, dayIndex }).then(() => undefined)}
            onDelete={(assignmentId) => deleteMutation.mutateAsync(assignmentId).then(() => undefined)}
            onUpdateLevel={(assignmentId, levelName) => updateLevelMutation.mutateAsync({ assignmentId, levelName }).then(() => undefined)}
          />

          {/* ── REVISION HISTORY ── */}
          {revisionHistory.length > 0 && (
            <div>
              <button
                onClick={() => setShowHistory((v) => !v)}
                className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-xs tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-0.5 active:translate-y-0.5 active:shadow-none"
              >
                {showHistory ? "Hide" : "Show"} Revision History ({revisionHistory.length})
              </button>

              {showHistory && (
                <div className="mt-3 border-4 border-neo-black bg-white shadow-neo-sm max-h-64 overflow-y-auto">
                  {revisionHistory.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-3 border-b-2 border-neo-black/10 px-4 py-3 last:border-0 hover:bg-neo-bg transition-colors">
                      <span className="border-2 border-neo-black px-2 py-0.5 text-[10px] font-black uppercase bg-neo-muted shrink-0">{entry.action}</span>
                      <div className="flex-1 min-w-0">
                        {entry.change_summary && <p className="text-xs font-medium text-neo-black/70 truncate">{entry.change_summary}</p>}
                        <p className="text-[10px] text-neo-black/40 mt-0.5">{new Date(entry.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
