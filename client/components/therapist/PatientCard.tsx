import { NeoButton } from "@/components/ui/NeoButton";
import { Patient } from "@/types";
import Link from "next/link";

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    approved: "bg-neo-secondary border-neo-black text-neo-black",
    pending: "bg-neo-muted border-neo-black text-neo-black",
    rejected: "bg-neo-accent border-neo-black text-neo-black",
  };
  const icons: Record<string, string> = { approved: "✓", pending: "⏳", rejected: "✕" };
  const cls = styles[status] ?? "bg-white border-neo-black";
  return (
    <span className={`border-2 px-2 py-0.5 text-xs font-black uppercase tracking-widest ${cls}`}>
      {icons[status] ?? ""} {status}
    </span>
  );
}

export function PatientCard({ patient }: { patient: Patient }) {
  const initials = getInitials(patient.full_name);
  const defectCount = patient.pre_assigned_defect_ids?.defect_ids.length ?? 0;

  return (
    <div className="border-4 border-neo-black bg-white shadow-neo-md hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo-lg transition-all duration-200 flex flex-col">
      {/* Header stripe */}
      <div className={`border-b-4 border-neo-black px-4 py-3 flex items-center justify-between ${
        patient.status === "approved" ? "bg-neo-secondary" : patient.status === "pending" ? "bg-neo-muted" : "bg-neo-accent"
      }`}>
        {/* Avatar initials */}
        <div className="w-10 h-10 border-4 border-neo-black bg-white flex items-center justify-center font-black text-sm shadow-neo-sm shrink-0">
          {initials}
        </div>
        <StatusBadge status={patient.status} />
      </div>

      {/* Body */}
      <div className="p-4 flex-1 space-y-3">
        <div>
          <h3 className="font-black text-lg uppercase leading-tight">{patient.full_name}</h3>
          <p className="text-xs font-medium text-neo-black/60 truncate">{patient.email}</p>
        </div>

        {/* Info grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="border-2 border-neo-black px-2 py-1.5 bg-neo-bg">
            <p className="font-black uppercase text-neo-black/50 text-[10px] mb-0.5">DOB</p>
            <p className="font-bold">{patient.date_of_birth ?? "—"}</p>
          </div>
          <div className="border-2 border-neo-black px-2 py-1.5 bg-neo-bg">
            <p className="font-black uppercase text-neo-black/50 text-[10px] mb-0.5">Gender</p>
            <p className="font-bold capitalize">{patient.gender ?? "—"}</p>
          </div>
        </div>

        {/* Defect count */}
        {defectCount > 0 && (
          <div className="flex items-center gap-2">
            <span className="border-2 border-neo-black bg-neo-accent px-2 py-0.5 text-xs font-black uppercase">
              {defectCount} condition{defectCount !== 1 ? "s" : ""}
            </span>
          </div>
        )}

      </div>

      {/* Footer action */}
      <div className="border-t-4 border-neo-black p-3">
        <Link href={`/therapist/patients/${patient.patient_id}`} className="block">
          <NeoButton size="sm" variant="ghost" className="w-full group">
            <span className="group-hover:mr-1 transition-all">View Details</span>
            <span className="opacity-0 group-hover:opacity-100 transition-opacity"> →</span>
          </NeoButton>
        </Link>
      </div>
    </div>
  );
}
