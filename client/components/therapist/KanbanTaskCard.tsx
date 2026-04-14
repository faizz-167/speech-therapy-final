import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { Assignment } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoSelect } from "@/components/ui/NeoSelect";

interface Props {
  assignment: Assignment;
  onDelete: (id: string) => void;
  onUpdateLevel: (id: string, levelName: string) => Promise<void>;
}

const LEVEL_OPTIONS = ["beginner", "intermediate", "advanced"];

export function KanbanTaskCard({ assignment, onDelete, onUpdateLevel }: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: assignment.assignment_id });

  const style = {
    transform: transform ? CSS.Transform.toString(transform) : undefined,
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  const [editingLevel, setEditingLevel] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState(assignment.initial_level_name ?? "beginner");

  // Deterministic color based on task name length
  const colors = ["bg-neo-secondary", "bg-neo-accent", "bg-neo-primary", "bg-white", "bg-neo-warning"];
  const bgColor = colors[(assignment.task_name?.length || 0) % colors.length];

  async function handleSaveLevel() {
    await onUpdateLevel(assignment.assignment_id, selectedLevel);
    setEditingLevel(false);
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className={`border-4 border-neo-black ${bgColor} shadow-neo-sm p-3 space-y-1 group hover:-translate-y-1 hover:shadow-neo-md transition-all`}
    >
      <div className="flex items-start justify-between gap-2">
        <div {...listeners} className="cursor-grab flex-1">
          <div className="flex items-center gap-2 mb-1 opacity-50 font-black">
             <span>∷</span>
          </div>
          <p className="font-black text-sm uppercase leading-tight">
            {assignment.task_name}
          </p>
          <p className="text-xs font-bold opacity-80 mt-1">
            {assignment.task_mode}
          </p>
          <div className="mt-2">
            <span className="inline-flex border-2 border-neo-black bg-white px-2 py-0.5 text-[10px] font-black uppercase">
              Level: {assignment.initial_level_name ?? "unset"}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <button
            onClick={() => setEditingLevel((value) => !value)}
            className="border-2 border-neo-black min-w-8 h-6 flex flex-shrink-0 items-center justify-center px-1 text-[10px] font-black bg-white hover:bg-neo-secondary transition-colors"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(assignment.assignment_id)}
            className="border-2 border-neo-black w-6 h-6 flex flex-shrink-0 items-center justify-center font-black bg-white hover:bg-neo-accent transition-colors"
          >
            ✕
          </button>
        </div>
      </div>
      {editingLevel && (
        <div className="space-y-2 border-t-2 border-neo-black pt-2">
          <NeoSelect
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="w-full border-2 border-neo-black bg-white px-2 py-2 text-xs font-bold uppercase"
          >
            {LEVEL_OPTIONS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </NeoSelect>
          <div className="flex gap-2">
            <NeoButton size="sm" onClick={() => void handleSaveLevel()} className="flex-1 py-1 text-xs">
              Save
            </NeoButton>
            <NeoButton
              size="sm"
              variant="ghost"
              onClick={() => {
                setSelectedLevel(assignment.initial_level_name ?? "beginner");
                setEditingLevel(false);
              }}
              className="flex-1 py-1 text-xs"
            >
              Cancel
            </NeoButton>
          </div>
        </div>
      )}
    </div>
  );
}
