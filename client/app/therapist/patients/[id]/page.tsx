"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Patient, Defect } from "@/types";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import Link from "next/link";

export default function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [defects, setDefects] = useState<Defect[]>([]);
  const [selectedDefects, setSelectedDefects] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [validationMsg, setValidationMsg] = useState("");
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<Patient>(`/therapist/patients/${id}`),
      api.get<Defect[]>("/therapist/defects"),
    ]).then(([p, d]) => { setPatient(p); setDefects(d); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleApprove() {
    if (selectedDefects.length === 0) { setValidationMsg("Select at least one defect"); return; }
    setValidationMsg("");
    setApproving(true);
    try {
      await api.post(`/therapist/patients/${id}/approve`, { defect_ids: selectedDefects });
      const updated = await api.get<Patient>(`/therapist/patients/${id}`);
      setPatient(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally { setApproving(false); }
  }

  function handleReject() {
    setShowRejectConfirm(true);
  }

  async function doReject() {
    try {
      await api.post(`/therapist/patients/${id}/reject`, {});
      router.push("/therapist/patients");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  if (loading) return <LoadingState label="Loading patient details..." />;
  if (error) return <ErrorState message={error} />;
  if (!patient) {
    return (
      <EmptyState
        icon="🧑"
        heading="Patient Not Found"
        subtext="This patient record is no longer available."
      />
    );
  }

  return (
    <div className="space-y-6 animate-fade-up max-w-2xl">
      <ConfirmModal
        open={showRejectConfirm}
        title="Reject Patient"
        message="Reject and remove this patient? This cannot be undone."
        confirmLabel="Reject"
        cancelLabel="Keep"
        dangerous
        onConfirm={() => { setShowRejectConfirm(false); doReject(); }}
        onCancel={() => setShowRejectConfirm(false)}
      />
      <h1 className="text-3xl font-black uppercase">{patient.full_name}</h1>
      <NeoCard className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-sm font-medium">
          <span className="font-black uppercase">Email:</span><span>{patient.email}</span>
          <span className="font-black uppercase">DOB:</span><span>{patient.date_of_birth}</span>
          <span className="font-black uppercase">Gender:</span><span>{patient.gender ?? "—"}</span>
          <span className="font-black uppercase">Status:</span>
          <span className={`font-black uppercase ${patient.status === "approved" ? "text-green-700" : "text-orange-600"}`}>{patient.status}</span>
        </div>
        {(() => {
          const assignedDefectIds = patient.pre_assigned_defect_ids?.defect_ids ?? [];
          const assignedDefects = defects.filter(d => assignedDefectIds.includes(d.defect_id));
          if (assignedDefects.length === 0) return null;
          return (
            <div className="border-t-4 border-black pt-3 space-y-2">
              <p className="font-black uppercase text-xs text-gray-500">Assigned Conditions</p>
              <div className="flex flex-wrap gap-2">
                {assignedDefects.map(d => (
                  <span key={d.defect_id} className="border-2 border-black px-3 py-1 text-sm font-bold bg-[#FFD93D]">
                    {d.name} <span className="text-xs font-medium text-gray-600">({d.category})</span>
                  </span>
                ))}
              </div>
            </div>
          );
        })()}
      </NeoCard>

      {patient.status === "pending" && (
        <NeoCard accent="secondary" className="space-y-4">
          <h2 className="font-black uppercase">Approve Patient</h2>
          <p className="text-sm font-medium">Select defects for this patient:</p>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {defects.map((d) => (
              <label key={d.defect_id} className="flex items-center gap-2 font-medium cursor-pointer">
                <input type="checkbox" className="w-4 h-4"
                  checked={selectedDefects.includes(d.defect_id)}
                  onChange={(e) => {
                    setValidationMsg("");
                    setSelectedDefects(prev =>
                      e.target.checked ? [...prev, d.defect_id] : prev.filter(x => x !== d.defect_id)
                    );
                  }}
                />
                <span>{d.name} <span className="text-xs text-gray-500">({d.category})</span></span>
              </label>
            ))}
          </div>
          {validationMsg && (
            <p className="text-sm font-bold text-red-600">{validationMsg}</p>
          )}
          <div className="flex gap-3">
            <NeoButton onClick={handleApprove} disabled={approving} className="flex-1">
              {approving ? "Approving..." : "Approve"}
            </NeoButton>
            <NeoButton variant="ghost" onClick={handleReject} className="flex-1">Reject</NeoButton>
          </div>
        </NeoCard>
      )}

      {patient.status === "approved" && (
        <div className="flex gap-3">
          <Link href={`/therapist/patients/${id}/baseline`}><NeoButton variant="ghost">View Baseline</NeoButton></Link>
          <Link href={`/therapist/patients/${id}/plan`}><NeoButton>Manage Plan</NeoButton></Link>
          <Link href={`/therapist/patients/${id}/progress`}><NeoButton variant="secondary">Progress</NeoButton></Link>
        </div>
      )}
    </div>
  );
}
