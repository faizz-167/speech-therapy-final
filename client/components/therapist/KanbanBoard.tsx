"use client";
import { useState } from "react";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor,
  useSensor, useSensors, closestCorners, useDroppable,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Assignment, Task } from "@/types";
import { KanbanTaskCard } from "./KanbanTaskCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoSelect } from "@/components/ui/NeoSelect";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_ACCENTS = [
  "bg-neo-accent", "bg-neo-secondary", "bg-neo-muted", "bg-neo-accent",
  "bg-neo-secondary", "bg-neo-muted", "bg-white",
];

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

function DayColumn({ dayIndex, assignments, availableTasks, onAdd, onDelete, onUpdateLevel }: DayColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: `day-${dayIndex}` });
  const [adding, setAdding] = useState(false);
  const [selectedTask, setSelectedTask] = useState("");
  const headerAccent = DAY_ACCENTS[dayIndex % DAY_ACCENTS.length];

  async function handleAdd() {
    if (!selectedTask) return;
    try {
      await onAdd(selectedTask, dayIndex);
      setSelectedTask("");
      setAdding(false);
    } catch { /* handled by page-level toast */ }
  }

  return (
    <div className="flex flex-col min-w-[140px]">
      {/* Day header */}
      <div className={`${headerAccent} border-4 border-neo-black px-2 py-2 font-black uppercase text-center tracking-widest text-xs shadow-neo-sm`}>
        {DAYS[dayIndex]}
        {assignments.length > 0 && (
          <div className="mt-0.5 font-bold text-neo-black/50 text-[9px] tracking-normal normal-case">
            {assignments.length} task{assignments.length !== 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        ref={setNodeRef}
        className={`flex-1 p-2 space-y-2 min-h-[280px] border-4 border-t-0 border-neo-black transition-colors ${
          isOver ? "bg-neo-secondary/30" : "bg-neo-bg/50"
        }`}
      >
        <SortableContext items={assignments.map((a) => a.assignment_id)} strategy={verticalListSortingStrategy}>
          {assignments.map((a) => (
            <KanbanTaskCard key={a.assignment_id} assignment={a} onDelete={onDelete} onUpdateLevel={onUpdateLevel} />
          ))}
        </SortableContext>

        {/* Add task slot */}
        <div className="mt-auto pt-2">
          {adding ? (
            <div className="border-4 border-dashed border-neo-black p-2 space-y-2 bg-white">
              <NeoSelect
                value={selectedTask}
                onChange={(e) => setSelectedTask(e.target.value)}
                className="w-full text-[10px] h-9 px-1 border-2"
              >
                <option value="">Pick task…</option>
                {availableTasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>{t.name}</option>
                ))}
              </NeoSelect>
              <div className="flex gap-1">
                <NeoButton size="sm" onClick={handleAdd} className="flex-1 h-8 text-[10px] py-0">Add</NeoButton>
                <NeoButton size="sm" variant="ghost" onClick={() => setAdding(false)} className="flex-1 h-8 text-[10px] py-0">✕</NeoButton>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setAdding(true)}
              className="w-full border-[3px] border-dashed border-neo-black text-neo-black font-black uppercase text-[10px] py-2 hover:bg-neo-secondary hover:border-solid transition-colors"
            >
              + Add
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function KanbanBoard({ assignments, availableTasks, onMove, onAdd, onDelete, onUpdateLevel }: Props) {
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
      const assignment = assignments.find((a) => a.assignment_id === String(active.id));
      if (assignment && assignment.day_index !== newDayIndex) {
        void onMove(String(active.id), newDayIndex).catch(() => {});
      }
    }
  }

  const byDay = (day: number) => assignments.filter((a) => a.day_index === day);

  return (
    <div className="border-4 border-neo-black bg-white shadow-neo-md overflow-hidden">
      {/* Board header */}
      <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 bg-neo-secondary inline-block border-2 border-white"></span>
          Weekly Schedule
        </div>
        <span className="text-white/50 font-bold text-xs normal-case tracking-normal">Drag tasks between days</span>
      </div>

      {/* Kanban columns */}
      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-7 overflow-x-auto" style={{ minWidth: "980px" }}>
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

      {/* Footer */}
      <div className="border-t-4 border-neo-black px-5 py-2 bg-neo-bg">
        <p className="text-[10px] font-bold text-neo-black/40">
          {assignments.length} task{assignments.length !== 1 ? "s" : ""} scheduled across {DAYS.filter((_, i) => byDay(i).length > 0).length} day{DAYS.filter((_, i) => byDay(i).length > 0).length !== 1 ? "s" : ""}
        </p>
      </div>
    </div>
  );
}
