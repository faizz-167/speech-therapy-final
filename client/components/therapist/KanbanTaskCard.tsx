import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { Assignment } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { NeoSelect } from "@/components/ui/NeoSelect";

interface Props {
  assignment: Assignment;
  onDelete: (id: string) => Promise<void>;
  onUpdateLevel: (id: string, levelName: string) => Promise<void>;
}

const LEVEL_OPTIONS = ["beginner", "intermediate", "advanced"];

const LEVEL_ACCENT: Record<string, string> = {
  beginner: "bg-neo-secondary",
  intermediate: "bg-neo-muted",
  advanced: "bg-neo-accent",
};

const CARD_COLORS = ["bg-neo-secondary", "bg-neo-muted", "bg-white", "bg-neo-accent"];

export function KanbanTaskCard({ assignment, onDelete, onUpdateLevel }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: assignment.assignment_id });

  const style = {
    transform: transform ? CSS.Transform.toString(transform) : undefined,
    transition,
    opacity: isDragging ? 0.4 : 1,
    zIndex: isDragging ? 50 : undefined,
  };

  const [editingLevel, setEditingLevel] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState(assignment.initial_level_name ?? "beginner");

  const cardBg = CARD_COLORS[(assignment.task_name?.length || 0) % CARD_COLORS.length];
  const levelAccent = LEVEL_ACCENT[(assignment.initial_level_name ?? "").toLowerCase()] ?? "bg-white";

  async function handleSaveLevel() {
    try {
      await onUpdateLevel(assignment.assignment_id, selectedLevel);
      setEditingLevel(false);
    } catch {
      // toast handled at page level
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className={`border-4 border-neo-black ${cardBg} ${isDragging ? "shadow-neo-lg rotate-2" : "shadow-neo-sm hover:-translate-y-0.5 hover:shadow-neo-md"} transition-all duration-150`}
    >
      {/* Drag handle row */}
      <div {...listeners} className="cursor-grab active:cursor-grabbing px-3 pt-2 pb-1 flex items-center gap-1.5 border-b-2 border-neo-black/15">
        <span className="font-black text-neo-black/30 text-sm leading-none">∷</span>
        <span className="font-black uppercase text-[9px] tracking-widest text-neo-black/30">drag</span>
      </div>

      {/* Card body */}
      <div className="px-3 py-2 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-black text-xs uppercase leading-tight truncate">{assignment.task_name}</p>
            {assignment.task_mode && (
              <p className="text-[10px] font-bold text-neo-black/50 mt-0.5">{assignment.task_mode}</p>
            )}
          </div>
          <div className="flex gap-1 shrink-0">
            <button
              onClick={() => setEditingLevel((v) => !v)}
              className="border-2 border-neo-black bg-white w-6 h-6 flex items-center justify-center font-black text-[10px] hover:bg-neo-secondary transition-colors"
              aria-label="Edit level"
            >
              ✎
            </button>
            <button
              onClick={() => { void onDelete(assignment.assignment_id).catch(() => {}); }}
              className="border-2 border-neo-black bg-white w-6 h-6 flex items-center justify-center font-black text-[10px] hover:bg-neo-accent transition-colors"
              aria-label="Remove task"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Level badge */}
        {!editingLevel && (
          <div className={`inline-flex border-2 border-neo-black px-2 py-0.5 text-[9px] font-black uppercase ${levelAccent}`}>
            {assignment.initial_level_name ?? "unset"}
          </div>
        )}

        {/* Level editor */}
        {editingLevel && (
          <div className="space-y-2 border-t-2 border-neo-black/20 pt-2">
            <NeoSelect
              value={selectedLevel}
              onChange={(e) => setSelectedLevel(e.target.value)}
              className="w-full border-2 border-neo-black bg-white px-2 py-1.5 text-xs font-bold uppercase"
            >
              {LEVEL_OPTIONS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </NeoSelect>
            <div className="flex gap-1.5">
              <NeoButton size="sm" onClick={() => void handleSaveLevel()} className="flex-1 h-7 text-[10px] py-0">Save</NeoButton>
              <NeoButton size="sm" variant="ghost" onClick={() => { setSelectedLevel(assignment.initial_level_name ?? "beginner"); setEditingLevel(false); }} className="flex-1 h-7 text-[10px] py-0">Cancel</NeoButton>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
