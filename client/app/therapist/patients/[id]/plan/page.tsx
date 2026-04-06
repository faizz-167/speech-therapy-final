"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Plan, Task, Assignment } from "@/types";
import { KanbanBoard } from "@/components/therapist/KanbanBoard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";
import Link from "next/link";

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
    <div className="space-y-6 animate-fade-up pt-4">
      <div className="flex items-center gap-4 mb-8">
          <Link href={`/therapist/patients/${id}`} className="font-black uppercase tracking-widest text-sm border-4 border-neo-black px-4 py-2 bg-white hover:bg-neo-secondary transition-colors shadow-neo-sm">
             ← BACK
          </Link>
      </div>

      {!plan ? (
        <div className="bg-white border-4 border-neo-black p-8 text-center shadow-neo-sm">
          <span className="text-4xl block mb-4">📝</span>
          <p className="font-black uppercase text-xl">
            No plan exists for this patient yet.<br/>Click Generate Plan above to construct a weekly progression framework.
          </p>
          <NeoButton variant="secondary" onClick={handleGenerate} disabled={generating} className="mt-6 bg-neo-warning text-neo-black shadow-neo-sm">
             {generating ? "GENERATING..." : "🔄 GENERATE NEW PLAN"}
          </NeoButton>
        </div>
      ) : (
        <>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-4 border-neo-black pb-4">
             <div>
                <h2 className="font-black text-3xl uppercase tracking-tighter shadow-neo-sm border-2 border-transparent inline-block bg-white px-2 py-1 rotate-1">{plan.plan_name || `Week of ${plan.start_date}`}</h2>
                <div className="font-bold tracking-widest text-sm mt-3 uppercase">
                  {plan.start_date} — {plan.end_date}
                </div>
             </div>
             
             <div className="flex flex-wrap gap-2 mt-4 md:mt-0">
                 {plan.status === "approved" && <span className="bg-neo-primary border-4 border-neo-black px-4 py-2 font-black uppercase text-sm shadow-neo-sm text-neo-black flex items-center tracking-widest">APPROVED</span>}
                 {plan.status === "draft" && <NeoButton onClick={handleApprove} disabled={approving} className="shadow-neo-sm bg-neo-primary text-neo-black tracking-widest hover:text-white">{approving ? "APPROVING..." : "APPROVE PLAN"}</NeoButton>}
                 <NeoButton variant="secondary" onClick={handleGenerate} disabled={generating} className="bg-neo-warning text-neo-black tracking-widest shadow-neo-sm hover:bg-neo-black hover:text-neo-warning transition-colors">
                    {generating ? "GENERATING..." : "🔄 REGENERATE"}
                 </NeoButton>
                 <NeoButton className="bg-neo-accent text-neo-black shadow-neo-sm hover:text-white tracking-widest">🗑 DELETE PLAN</NeoButton>
             </div>
          </div>
          
          <div className="bg-neo-primary/40 border-4 border-neo-black px-4 py-3 font-bold text-sm shadow-neo-sm -rotate-1 mb-8">
             {plan.status === "approved" ? "This plan is approved and visible to the patient. You can still drag tasks between days, add new tasks, or remove tasks at any time." : "This plan is a draft. The patient cannot see it until you approve it."}
          </div>

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
