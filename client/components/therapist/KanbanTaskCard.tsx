import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Assignment } from "@/types";

interface Props {
  assignment: Assignment;
  onDelete: (id: string) => void;
}

export function KanbanTaskCard({ assignment, onDelete }: Props) {
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

  // Deterministic color based on task name length
  const colors = ["bg-neo-secondary", "bg-neo-accent", "bg-neo-primary", "bg-white", "bg-neo-warning"];
  const bgColor = colors[(assignment.task_name?.length || 0) % colors.length];

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
        </div>
        <button
          onClick={() => onDelete(assignment.assignment_id)}
          className="border-2 border-neo-black w-6 h-6 flex flex-shrink-0 items-center justify-center font-black bg-white hover:bg-neo-accent transition-colors"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
