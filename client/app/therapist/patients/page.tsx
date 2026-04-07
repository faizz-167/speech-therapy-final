"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Patient } from "@/types";
import { PatientCard } from "@/components/therapist/PatientCard";
import { SkeletonList } from "@/components/ui/Skeletons";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Patient[]>("/therapist/patients")
      .then(setPatients)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <SkeletonList />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">Patients</h1>
      {patients.length === 0 ? (
        <EmptyState message="No patients yet." hint="Share your therapist code for patients to register." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map((p) => <PatientCard key={p.patient_id} patient={p} />)}
        </div>
      )}
    </div>
  );
}
