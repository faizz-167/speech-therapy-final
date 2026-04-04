"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Plan, Task, Assignment } from "@/types";
import { KanbanBoard } from "@/components/therapist/KanbanBoard";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoCard } from "@/components/ui/NeoCard";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [availableTasks, setAvailableTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);

  async function loadPlan() {
    try {
      const p = await api.get<Plan | null>(`/plans/patient/${id}/current`);
      setPlan(p);
      if (p) {
        const tasks = await api.get<Task[]>(
          `/plans/${p.plan_id}/tasks-for-defects`
        );
        setAvailableTasks(tasks);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const baseline = await api.get<{ level: string } | null>(
        `/baseline/therapist-view/${id}`
      );
      const level =
        (baseline as { level?: string } | null)?.level ?? "easy";
      const newPlan = await api.post<Plan>("/plans/generate", {
        patient_id: id,
        baseline_level: level,
      });
      setPlan(newPlan);
      const tasks = await api.get<Task[]>(
        `/plans/${newPlan.plan_id}/tasks-for-defects`
      );
      setAvailableTasks(tasks);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleMove(assignmentId: string, newDayIndex: number) {
    if (!plan) return;
    await api.patch(`/plans/${plan.plan_id}/tasks/${assignmentId}`, {
      day_index: newDayIndex,
    });
    setPlan((prev) =>
      prev
        ? {
            ...prev,
            assignments: prev.assignments.map((a) =>
              a.assignment_id === assignmentId
                ? { ...a, day_index: newDayIndex }
                : a
            ),
          }
        : prev
    );
  }

  async function handleAdd(taskId: string, dayIndex: number) {
    if (!plan) return;
    const newAssignment = await api.post<Assignment>(
      `/plans/${plan.plan_id}/tasks`,
      { task_id: taskId, day_index: dayIndex }
    );
    setPlan((prev) =>
      prev
        ? { ...prev, assignments: [...prev.assignments, newAssignment] }
        : prev
    );
  }

  async function handleDelete(assignmentId: string) {
    if (!plan) return;
    await api.delete(`/plans/${plan.plan_id}/tasks/${assignmentId}`);
    setPlan((prev) =>
      prev
        ? {
            ...prev,
            assignments: prev.assignments.filter(
              (a) => a.assignment_id !== assignmentId
            ),
          }
        : prev
    );
  }

  async function handleApprove() {
    if (!plan) return;
    setApproving(true);
    try {
      await api.post(`/plans/${plan.plan_id}/approve`, {});
      setPlan((prev) => (prev ? { ...prev, status: "approved" } : prev));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setApproving(false);
    }
  }

  if (loading) return <SkeletonList />;
  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black uppercase">Therapy Plan</h1>
        <div className="flex gap-3">
          <NeoButton
            variant="ghost"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating..." : plan ? "Regenerate" : "Generate Plan"}
          </NeoButton>
          {plan && plan.status === "draft" && (
            <NeoButton onClick={handleApprove} disabled={approving}>
              {approving ? "Approving..." : "Approve Plan"}
            </NeoButton>
          )}
          {plan && plan.status === "approved" && (
            <span className="border-4 border-black bg-[#FFD93D] px-4 py-2 font-black uppercase text-sm">
              Approved
            </span>
          )}
        </div>
      </div>

      {!plan ? (
        <NeoCard>
          <p className="font-bold">
            No plan yet. Click Generate Plan to create a weekly therapy plan.
          </p>
        </NeoCard>
      ) : (
        <>
          <NeoCard className="space-y-1">
            <p className="font-black">{plan.plan_name}</p>
            <p className="text-sm font-medium">
              {plan.start_date} → {plan.end_date}
            </p>
            {plan.goals && (
              <p className="text-sm font-medium text-gray-600">{plan.goals}</p>
            )}
          </NeoCard>
          <KanbanBoard
            assignments={plan.assignments}
            availableTasks={availableTasks}
            onMove={handleMove}
            onAdd={handleAdd}
            onDelete={handleDelete}
          />
        </>
      )}
    </div>
  );
}
