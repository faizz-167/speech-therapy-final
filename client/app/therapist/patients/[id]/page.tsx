"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Patient, Defect, ApproveRequest } from "@/types";
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
  const qc = useQueryClient();
  const [selectedDefects, setSelectedDefects] = useState<string[]>([]);
  const [primaryDiagnosis, setPrimaryDiagnosis] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [validationMsg, setValidationMsg] = useState("");
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);

  const { data: patient, error: patientError, isLoading: patientLoading } = useQuery<Patient>({
    queryKey: ["therapist", "patient", id],
    queryFn: () => api.get<Patient>(`/therapist/patients/${id}`),
  });

  const { data: defects = [], isLoading: defectsLoading } = useQuery<Defect[]>({
    queryKey: ["therapist", "defects"],
    queryFn: () => api.get<Defect[]>("/therapist/defects"),
  });

  const approveMutation = useMutation({
    mutationFn: async () => {
      const body: ApproveRequest = { defect_ids: selectedDefects };
      if (primaryDiagnosis.trim()) body.primary_diagnosis = primaryDiagnosis.trim();
      if (clinicalNotes.trim()) body.clinical_notes = clinicalNotes.trim();
      await api.post(`/therapist/patients/${id}/approve`, body);
    },
    onSuccess: () => {
      toast.success("Patient approved successfully.");
      qc.invalidateQueries({ queryKey: ["therapist", "patient", id] });
      qc.invalidateQueries({ queryKey: ["therapist", "patients"] });
      qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] });
    },
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "Approval failed");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/therapist/patients/${id}/reject`, {}),
    onSuccess: () => {
      toast.success("Patient rejected.");
      qc.invalidateQueries({ queryKey: ["therapist", "patients"] });
      qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] });
      router.push("/therapist/patients");
    },
    onError: (e: unknown) => {
      toast.error(e instanceof Error ? e.message : "Rejection failed");
    },
  });

  function handleApprove() {
    if (selectedDefects.length === 0) { setValidationMsg("Select at least one defect"); return; }
    setValidationMsg("");
    approveMutation.mutate();
  }

  const isLoading = patientLoading || defectsLoading;

  if (isLoading) return <LoadingState label="Loading patient details..." />;
  if (patientError) return <ErrorState message={patientError instanceof Error ? patientError.message : "Failed to load"} />;
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
        onConfirm={() => { setShowRejectConfirm(false); rejectMutation.mutate(); }}
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
          const assignedDefectsList = defects.filter(d => assignedDefectIds.includes(d.defect_id));
          if (assignedDefectsList.length === 0) return null;
          return (
            <div className="border-t-4 border-black pt-3 space-y-2">
              <p className="font-black uppercase text-xs text-neo-black/70">Assigned Conditions</p>
              <div className="flex flex-wrap gap-2">
                {assignedDefectsList.map(d => (
                  <span key={d.defect_id} className="border-2 border-black px-3 py-1 text-sm font-bold bg-[#FFD93D]">
                    {d.name} <span className="text-xs font-medium text-neo-black/70">({d.category})</span>
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
                <span>{d.name} <span className="text-xs text-neo-black/70">({d.category})</span></span>
              </label>
            ))}
          </div>

          <div className="space-y-1">
            <label htmlFor="primary-diagnosis" className="font-black uppercase text-xs">Primary Diagnosis</label>
            <input
              id="primary-diagnosis"
              type="text"
              value={primaryDiagnosis}
              onChange={(e) => setPrimaryDiagnosis(e.target.value)}
              placeholder="e.g. Articulation Disorder"
              className="w-full border-4 border-black px-3 py-2 font-medium text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="clinical-notes" className="font-black uppercase text-xs">Clinical Notes <span className="text-neo-black/70 font-medium normal-case">(optional)</span></label>
            <textarea
              id="clinical-notes"
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
              placeholder="Any relevant clinical observations..."
              rows={3}
              className="w-full border-4 border-black px-3 py-2 font-medium text-sm focus:outline-none focus:ring-2 focus:ring-neo-accent resize-none"
            />
          </div>

          {validationMsg && (
            <p className="text-sm font-bold text-red-600">{validationMsg}</p>
          )}
          <div className="flex gap-3">
            <NeoButton onClick={handleApprove} disabled={approveMutation.isPending} className="flex-1">
              {approveMutation.isPending ? "Approving..." : "Approve"}
            </NeoButton>
            <NeoButton variant="ghost" onClick={() => setShowRejectConfirm(true)} className="flex-1">Reject</NeoButton>
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
