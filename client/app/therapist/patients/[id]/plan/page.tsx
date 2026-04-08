"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Plan, Task, Assignment, PlanRevisionEntry } from "@/types";
import { KanbanBoard } from "@/components/therapist/KanbanBoard";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
      qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] });
      toast.success("Task moved.");
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Move failed"),
  });

  const addMutation = useMutation({
    mutationFn: ({ taskId, dayIndex }: { taskId: string; dayIndex: number }) =>
      api.post<Assignment>(`/plans/${plan!.plan_id}/tasks`, { task_id: taskId, day_index: dayIndex }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
      qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] });
      toast.success("Task added.");
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Add failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      api.delete(`/plans/${plan!.plan_id}/tasks/${assignmentId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
      qc.invalidateQueries({ queryKey: ["therapist", "plan-revisions", plan?.plan_id] });
      toast.success("Task removed.");
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Delete failed"),
  });

  const approveMutation = useMutation({
    mutationFn: () => api.post(`/plans/${plan!.plan_id}/approve`, {}),
    onSuccess: () => {
      toast.success("Plan approved and visible to patient.");
      qc.invalidateQueries({ queryKey: ["therapist", "plan", id] });
      qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] });
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Approval failed"),
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

  const isMutating = moveMutation.isPending || addMutation.isPending || deleteMutation.isPending;
  const mutationState = isMutating ? "saving" : "idle";

  if (isLoading) return <LoadingState label="Loading plan..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  return (
    <div className="space-y-6 animate-fade-up pt-4">
      <div className="flex items-center gap-4 mb-8">
          <Link href={`/therapist/patients/${id}`} className="font-black uppercase tracking-widest text-sm border-4 border-neo-black px-4 py-2 bg-white hover:bg-neo-secondary transition-colors shadow-neo-sm">
             ← BACK
          </Link>
      </div>

      {!plan ? (
        <EmptyState
          icon="📝"
          heading="No Plan Yet"
          subtext="Generate a weekly progression framework for this patient."
          cta={{
            label: generating ? "Generating..." : "Generate New Plan",
            onClick: handleGenerate,
          }}
        />
      ) : (
        <>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-4 border-neo-black pb-4">
             <div>
                <h2 className="font-black text-3xl uppercase tracking-tighter shadow-neo-sm border-2 border-transparent inline-block bg-white px-2 py-1 rotate-1">{plan.plan_name || `Week of ${plan.start_date ?? "TBD"}`}</h2>
                <div className="font-bold tracking-widest text-sm mt-3 uppercase">
                  {plan.start_date ?? "TBD"} — {plan.end_date ?? "TBD"}
                </div>
                {plan.goals && (
                  <p className="text-sm font-medium mt-2 text-gray-700 max-w-lg">{plan.goals}</p>
                )}
             </div>

             <div className="flex flex-wrap gap-2 mt-4 md:mt-0 items-center">
                 {mutationState === "saving" && (
                   <span className="text-xs font-bold uppercase tracking-widest text-gray-500 border-2 border-gray-300 px-3 py-2">Saving...</span>
                 )}
                 {plan.status === "approved" && <span className="bg-neo-primary border-4 border-neo-black px-4 py-2 font-black uppercase text-sm shadow-neo-sm text-neo-black flex items-center tracking-widest">APPROVED</span>}
                 {plan.status === "draft" && <NeoButton onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending} className="shadow-neo-sm bg-neo-primary text-neo-black tracking-widest hover:text-white">{approveMutation.isPending ? "APPROVING..." : "APPROVE PLAN"}</NeoButton>}
                 <NeoButton variant="secondary" onClick={handleGenerate} disabled={generating} className="bg-neo-warning text-neo-black tracking-widest shadow-neo-sm hover:bg-neo-black hover:text-neo-warning transition-colors">
                    {generating ? "GENERATING..." : "🔄 REGENERATE"}
                 </NeoButton>
             </div>
          </div>

          <div className="bg-neo-primary/40 border-4 border-neo-black px-4 py-3 font-bold text-sm shadow-neo-sm -rotate-1 mb-8">
             {plan.status === "approved" ? "This plan is approved and visible to the patient. You can still drag tasks between days, add new tasks, or remove tasks at any time." : "This plan is a draft. The patient cannot see it until you approve it."}
          </div>

          <KanbanBoard
            assignments={plan.assignments}
            availableTasks={availableTasks}
            onMove={(assignmentId, newDayIndex) => moveMutation.mutateAsync({ assignmentId, newDayIndex }).then(() => undefined)}
            onAdd={(taskId, dayIndex) => addMutation.mutateAsync({ taskId, dayIndex }).then(() => undefined)}
            onDelete={(assignmentId) => deleteMutation.mutateAsync(assignmentId).then(() => undefined)}
          />

          {revisionHistory.length > 0 && (
            <div className="mt-6">
              <button
                onClick={() => setShowHistory((v) => !v)}
                className="font-black uppercase tracking-widest text-sm border-4 border-neo-black px-4 py-2 bg-white hover:bg-neo-secondary transition-colors shadow-neo-sm"
              >
                {showHistory ? "Hide" : "Show"} Revision History ({revisionHistory.length})
              </button>
              {showHistory && (
                <NeoCard className="mt-3 space-y-2 max-h-72 overflow-y-auto">
                  {revisionHistory.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-3 border-b-2 border-gray-200 pb-2 last:border-0">
                      <span className="border-2 border-neo-black px-2 py-0.5 text-xs font-black uppercase bg-neo-muted whitespace-nowrap">{entry.action}</span>
                      <div className="flex-1 min-w-0">
                        {entry.change_summary && <p className="text-xs font-medium text-gray-700 truncate">{entry.change_summary}</p>}
                        <p className="text-xs text-gray-400">{new Date(entry.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </NeoCard>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
