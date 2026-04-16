"use client";
import { useState } from "react";
import {
  DndContext,
  DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  useDroppable,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
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
  onUpdateLevel: (assignmentId: string, levelName: string) => Promise<void>;
}

interface DayColumnProps {
  dayIndex: number;
  assignments: Assignment[];
  availableTasks: Task[];
  onAdd: (taskId: string, dayIndex: number) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onUpdateLevel: (assignmentId: string, levelName: string) => Promise<void>;
}

function DayColumn({
  dayIndex,
  assignments,
  availableTasks,
  onAdd,
  onDelete,
  onUpdateLevel,
}: DayColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: `day-${dayIndex}` });
  const [adding, setAdding] = useState(false);
  const [selectedTask, setSelectedTask] = useState("");

  async function handleAdd() {
    if (!selectedTask) return;
    try {
      await onAdd(selectedTask, dayIndex);
      setSelectedTask("");
      setAdding(false);
    } catch {
      // Mutation errors are handled by the page-level toast; avoid unhandled rejections here.
    }
  }

  return (
    <div className="flex flex-col min-h-[400px]">
      <div className="bg-neo-black text-white px-3 py-3 font-black uppercase text-center tracking-widest text-sm shadow-neo-sm">
        {DAYS[dayIndex]}
      </div>
      <div
        ref={setNodeRef}
        className={`flex-1 p-2 space-y-4 min-h-[300px] transition-colors ${
          isOver ? "bg-neo-secondary/20" : "bg-transparent"
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
              onUpdateLevel={onUpdateLevel}
            />
          ))}
        </SortableContext>
        
        {/* ADD SLOT AT BOTTOM */}
        <div className="pt-4 flex flex-col justify-end">
          {adding ? (
            <div className="space-y-2 border-4 border-dashed border-neo-black p-2 bg-white">
              <NeoSelect
                value={selectedTask}
                onChange={(e) => setSelectedTask(e.target.value)}
                className="w-full text-xs h-10 px-2 border-2"
              >
                <option value="">Select task...</option>
                {availableTasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>
                    {t.name}
                  </option>
                ))}
              </NeoSelect>
              <div className="flex gap-2">
                <NeoButton size="sm" onClick={handleAdd} className="flex-1 py-1 text-xs">
                  Add
                </NeoButton>
                <NeoButton
                  size="sm"
                  variant="ghost"
                  onClick={() => setAdding(false)}
                  className="flex-1 py-1 text-xs"
                >
                  Cancel
                </NeoButton>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setAdding(true)}
              className="w-full border-[3px] border-dashed border-neo-black text-neo-black font-black uppercase text-xs py-3 hover:bg-neo-black hover:text-white transition-colors shadow-none"
            >
              + Add
            </button>
          )}
        </div>
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
  onUpdateLevel,
}: Props) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
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
        void onMove(String(active.id), newDayIndex).catch(() => {
          // Mutation errors are handled by the page-level toast; avoid unhandled rejections here.
        });
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
      <div className="grid grid-cols-7 gap-4 overflow-x-auto pb-8">
        {DAYS.map((_, i) => (
          <DayColumn
            key={i}
            dayIndex={i}
            assignments={byDay(i)}
            availableTasks={availableTasks}
            onAdd={onAdd}
            onDelete={onDelete}
            onUpdateLevel={onUpdateLevel}
          />
        ))}
      </div>
    </DndContext>
  );
}
