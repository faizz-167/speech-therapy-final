"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Patient } from "@/types";
import { PatientCard } from "@/components/therapist/PatientCard";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

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
  if (error) return <ErrorBanner message={error} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">Patients</h1>
      {patients.length === 0 ? (
        <p className="font-bold text-gray-500">No patients yet. Share your therapist code for patients to register.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map((p) => <PatientCard key={p.patient_id} patient={p} />)}
        </div>
      )}
    </div>
  );
}
