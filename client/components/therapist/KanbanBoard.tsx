"use client";
import { useState } from "react";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  useDroppable,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Assignment, Task } from "@/types";
import { KanbanTaskCard } from "./KanbanTaskCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoSelect } from "@/components/ui/NeoSelect";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface Props {
  assignments: Assignment[];
  availableTasks: Task[];
  onMove: (assignmentId: string, newDayIndex: number) => Promise<void>;
  onAdd: (taskId: string, dayIndex: number) => Promise<void>;
  onDelete: (assignmentId: string) => Promise<void>;
}

interface DayColumnProps {
  dayIndex: number;
  assignments: Assignment[];
  availableTasks: Task[];
  onAdd: (taskId: string, dayIndex: number) => Promise<void>;
  onDelete: (id: string) => void;
}

function DayColumn({
  dayIndex,
  assignments,
  availableTasks,
  onAdd,
  onDelete,
}: DayColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: `day-${dayIndex}` });
  const [adding, setAdding] = useState(false);
  const [selectedTask, setSelectedTask] = useState("");

  async function handleAdd() {
    if (!selectedTask) return;
    await onAdd(selectedTask, dayIndex);
    setSelectedTask("");
    setAdding(false);
  }

  return (
    <div className="flex flex-col min-h-[300px]">
      <div className="border-4 border-black bg-[#FF6B6B] px-3 py-2 font-black uppercase text-center">
        {DAYS[dayIndex]}
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 border-4 border-t-0 border-black p-2 space-y-2 min-h-[200px] ${
          isOver ? "bg-[#FFD93D]/30" : "bg-white"
        }`}
      >
        <SortableContext
          items={assignments.map((a) => a.assignment_id)}
          strategy={verticalListSortingStrategy}
        >
          {assignments.map((a) => (
            <KanbanTaskCard
              key={a.assignment_id}
              assignment={a}
              onDelete={onDelete}
            />
          ))}
        </SortableContext>
        {adding ? (
          <div className="space-y-2">
            <NeoSelect
              value={selectedTask}
              onChange={(e) => setSelectedTask(e.target.value)}
              className="w-full text-xs"
            >
              <option value="">Select task...</option>
              {availableTasks.map((t) => (
                <option key={t.task_id} value={t.task_id}>
                  {t.name}
                </option>
              ))}
            </NeoSelect>
            <div className="flex gap-1">
              <NeoButton size="sm" onClick={handleAdd} className="flex-1">
                Add
              </NeoButton>
              <NeoButton
                size="sm"
                variant="ghost"
                onClick={() => setAdding(false)}
                className="flex-1"
              >
                Cancel
              </NeoButton>
            </div>
          </div>
        ) : (
          <NeoButton
            size="sm"
            variant="ghost"
            onClick={() => setAdding(true)}
            className="w-full border-dashed"
          >
            + Add
          </NeoButton>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard({
  assignments,
  availableTasks,
  onMove,
  onAdd,
  onDelete,
}: Props) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const overId = String(over.id);
    if (overId.startsWith("day-")) {
      const newDayIndex = parseInt(overId.replace("day-", ""), 10);
      const assignment = assignments.find(
        (a) => a.assignment_id === String(active.id)
      );
      if (assignment && assignment.day_index !== newDayIndex) {
        onMove(String(active.id), newDayIndex);
      }
    }
  }

  const byDay = (day: number) =>
    assignments.filter((a) => a.day_index === day);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-7 gap-2 overflow-x-auto">
        {DAYS.map((_, i) => (
          <DayColumn
            key={i}
            dayIndex={i}
            assignments={byDay(i)}
            availableTasks={availableTasks}
            onAdd={onAdd}
            onDelete={onDelete}
          />
        ))}
      </div>
    </DndContext>
  );
}
