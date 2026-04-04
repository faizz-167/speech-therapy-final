import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { Patient } from "@/types";
import Link from "next/link";

export function PatientCard({ patient }: { patient: Patient }) {
  return (
    <NeoCard hover className="space-y-2">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-black text-lg uppercase">{patient.full_name}</h3>
          <p className="text-sm font-medium text-gray-600">{patient.email}</p>
        </div>
        <span className={`px-2 py-1 text-xs font-black border-2 border-black uppercase ${
          patient.status === "approved" ? "bg-[#FFD93D]" : "bg-[#C4B5FD]"
        }`}>
          {patient.status}
        </span>
      </div>
      <p className="text-sm font-medium">DOB: {patient.date_of_birth}</p>
      {patient.pre_assigned_defect_ids && (
        <p className="text-sm font-medium">
          Defects: {patient.pre_assigned_defect_ids.defect_ids.length} assigned
        </p>
      )}
      <Link href={`/therapist/patients/${patient.patient_id}`}>
        <NeoButton size="sm" variant="ghost" className="w-full">View Details</NeoButton>
      </Link>
    </NeoCard>
  );
}
