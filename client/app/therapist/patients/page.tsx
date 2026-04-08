"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Patient } from "@/types";
import { PatientCard } from "@/components/therapist/PatientCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

export default function PatientsPage() {
  const { data: patients, error, isLoading } = useQuery<Patient[]>({
    queryKey: ["therapist", "patients"],
    queryFn: () => api.get<Patient[]>("/therapist/patients"),
  });

  if (isLoading) return <LoadingState label="Loading patients..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">Patients</h1>
      {!patients || patients.length === 0 ? (
        <EmptyState
          icon="🧑‍⚕️"
          heading="No Patients Yet"
          subtext="Share your therapist code for patients to register."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map((p) => <PatientCard key={p.patient_id} patient={p} />)}
        </div>
      )}
    </div>
  );
}
