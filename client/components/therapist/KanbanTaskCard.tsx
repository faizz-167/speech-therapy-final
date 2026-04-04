import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Assignment } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";

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

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      className="border-4 border-black bg-white shadow-[3px_3px_0px_0px_#000] p-3 space-y-1"
    >
      <div className="flex items-start justify-between gap-2">
        <div {...listeners} className="cursor-grab flex-1">
          <p className="font-black text-sm uppercase leading-tight">
            {assignment.task_name}
          </p>
          <p className="text-xs font-medium text-gray-500">
            {assignment.task_mode}
          </p>
        </div>
        <NeoButton
          size="sm"
          variant="ghost"
          onClick={() => onDelete(assignment.assignment_id)}
          className="!px-2 !py-0 text-xs border-2"
        >
          ✕
        </NeoButton>
      </div>
    </div>
  );
}
