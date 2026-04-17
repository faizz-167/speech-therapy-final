"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Patient, Defect, ApproveRequest } from "@/types";
import { NeoButton } from "@/components/ui/NeoButton";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import Link from "next/link";

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);
}

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
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Approval failed"),
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/therapist/patients/${id}/reject`, {}),
    onSuccess: () => {
      toast.success("Patient rejected.");
      qc.invalidateQueries({ queryKey: ["therapist", "patients"] });
      qc.invalidateQueries({ queryKey: ["therapist", "dashboard"] });
      router.push("/therapist/patients");
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : "Rejection failed"),
  });

  function handleApprove() {
    if (selectedDefects.length === 0) { setValidationMsg("Select at least one defect"); return; }
    setValidationMsg("");
    approveMutation.mutate();
  }

  const isLoading = patientLoading || defectsLoading;
  if (isLoading) return <LoadingState label="Loading patient details..." />;
  if (patientError) return <ErrorState message={patientError instanceof Error ? patientError.message : "Failed to load"} />;
  if (!patient) return <EmptyState icon="🧑" heading="Patient Not Found" subtext="This patient record is no longer available." />;

  const assignedDefectIds = patient.pre_assigned_defect_ids?.defect_ids ?? [];
  const assignedDefectsList = defects.filter((d) => assignedDefectIds.includes(d.defect_id));

  const statusAccent: Record<string, string> = {
    approved: "bg-neo-secondary",
    pending: "bg-neo-muted",
    rejected: "bg-neo-accent",
  };
  const statusBg = statusAccent[patient.status] ?? "bg-white";

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-4xl mx-auto space-y-8">
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

      {/* ── BACK ── */}
      <Link href="/therapist/patients" className="inline-flex items-center gap-2 border-4 border-neo-black bg-white px-4 py-2 font-black uppercase text-sm tracking-widest shadow-neo-sm hover:bg-neo-secondary transition-colors active:translate-x-1 active:translate-y-1 active:shadow-none">
        ← Back
      </Link>

      {/* ── HERO PROFILE CARD ── */}
      <div className="border-4 border-neo-black bg-white shadow-neo-lg overflow-hidden">
        {/* Color bar */}
        <div className={`${statusBg} border-b-4 border-neo-black px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4`}>
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 border-4 border-neo-black bg-white flex items-center justify-center font-black text-2xl shadow-neo-sm shrink-0 -rotate-2">
              {getInitials(patient.full_name)}
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-black uppercase tracking-tighter leading-none">{patient.full_name}</h1>
              <p className="font-medium text-neo-black/70 text-sm mt-1">{patient.email}</p>
            </div>
          </div>
          <div className="border-4 border-neo-black bg-white px-4 py-2 font-black uppercase tracking-widest text-sm shadow-neo-sm">
            {patient.status}
          </div>
        </div>

        {/* Details grid */}
        <div className="p-8 grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "Date of Birth", value: patient.date_of_birth ?? "—" },
            { label: "Gender", value: patient.gender ?? "—" },
            { label: "Registered", value: new Date(patient.created_at).toLocaleDateString() },
            { label: "Conditions", value: assignedDefectsList.length > 0 ? `${assignedDefectsList.length} assigned` : "—" },
          ].map(({ label, value }) => (
            <div key={label} className="border-2 border-neo-black px-3 py-2 bg-neo-bg">
              <p className="font-black uppercase text-[10px] tracking-widest text-neo-black/50 mb-1">{label}</p>
              <p className="font-bold text-sm capitalize">{value}</p>
            </div>
          ))}
        </div>

        {/* Assigned conditions */}
        {assignedDefectsList.length > 0 && (
          <div className="border-t-4 border-neo-black px-8 py-4">
            <p className="font-black uppercase text-xs tracking-widest text-neo-black/50 mb-3">Assigned Conditions</p>
            <div className="flex flex-wrap gap-2">
              {assignedDefectsList.map((d) => (
                <span key={d.defect_id} className="border-2 border-neo-black bg-neo-secondary px-3 py-1 text-xs font-black uppercase hover:rotate-1 transition-transform cursor-default">
                  {d.name}
                  <span className="font-medium text-neo-black/60 ml-1 normal-case">({d.category})</span>
                </span>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* ── APPROVAL FORM (pending only) ── */}
      {patient.status === "pending" && (
        <div className="border-4 border-neo-black bg-neo-secondary shadow-neo-md">
          <div className="bg-neo-black text-white px-6 py-3 font-black uppercase tracking-widest text-sm">
            Approve Patient
          </div>
          <div className="p-6 space-y-5">
            <p className="font-bold text-sm">Select the speech conditions that apply to this patient:</p>

            {/* Defect checkboxes */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-52 overflow-y-auto">
              {defects.map((d) => (
                <label key={d.defect_id} className={`flex items-center gap-3 border-2 px-3 py-2 cursor-pointer transition-colors ${
                  selectedDefects.includes(d.defect_id) ? "border-neo-black bg-neo-black text-white" : "border-neo-black bg-white hover:bg-neo-bg"
                }`}>
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={selectedDefects.includes(d.defect_id)}
                    onChange={(e) => {
                      setValidationMsg("");
                      setSelectedDefects((prev) =>
                        e.target.checked ? [...prev, d.defect_id] : prev.filter((x) => x !== d.defect_id)
                      );
                    }}
                  />
                  <span className={`w-4 h-4 border-2 flex items-center justify-center shrink-0 ${
                    selectedDefects.includes(d.defect_id) ? "border-white bg-white text-neo-black" : "border-neo-black bg-white"
                  }`}>
                    {selectedDefects.includes(d.defect_id) && <span className="text-[10px] font-black">✓</span>}
                  </span>
                  <div>
                    <p className="font-bold text-sm">{d.name}</p>
                    <p className="text-xs opacity-60">{d.category}</p>
                  </div>
                </label>
              ))}
            </div>

            {/* Primary diagnosis */}
            <div className="space-y-1">
              <label className="font-black uppercase text-xs tracking-widest">Primary Diagnosis</label>
              <input
                type="text"
                value={primaryDiagnosis}
                onChange={(e) => setPrimaryDiagnosis(e.target.value)}
                placeholder="e.g. Articulation Disorder"
                className="w-full border-4 border-neo-black bg-white px-3 py-2 font-medium text-sm focus:outline-none focus:bg-white focus:shadow-neo-sm"
              />
            </div>

            {/* Clinical notes */}
            <div className="space-y-1">
              <label className="font-black uppercase text-xs tracking-widest">
                Clinical Notes <span className="font-medium normal-case text-neo-black/50">(optional)</span>
              </label>
              <textarea
                value={clinicalNotes}
                onChange={(e) => setClinicalNotes(e.target.value)}
                placeholder="Any relevant clinical observations..."
                rows={3}
                className="w-full border-4 border-neo-black bg-white px-3 py-2 font-medium text-sm focus:outline-none focus:shadow-neo-sm resize-none"
              />
            </div>

            {validationMsg && (
              <div className="border-4 border-neo-black bg-neo-accent px-4 py-2 font-black text-sm">
                ⚠ {validationMsg}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <NeoButton onClick={handleApprove} disabled={approveMutation.isPending} className="flex-1">
                {approveMutation.isPending ? "Approving…" : "✓ Approve Patient"}
              </NeoButton>
              <NeoButton variant="ghost" onClick={() => setShowRejectConfirm(true)} className="flex-1">
                Reject
              </NeoButton>
            </div>
          </div>
        </div>
      )}

      {/* ── NAVIGATION TO SUB-PAGES (approved only) ── */}
      {patient.status === "approved" && (
        <div className="space-y-4">
          <h2 className="font-black uppercase tracking-widest text-sm border-b-4 border-neo-black pb-2">Patient Records</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { href: `/therapist/patients/${id}/baseline`, label: "Baseline", accent: "bg-neo-muted", icon: "🧪" },
              { href: `/therapist/patients/${id}/plan`, label: "Therapy Plan", accent: "bg-neo-accent", icon: "📋" },
              { href: `/therapist/patients/${id}/progress`, label: "Progress", accent: "bg-neo-secondary", icon: "📈" },
              { href: `/therapist/patients/${id}/adaptations`, label: "Adaptations", accent: "bg-white", icon: "⚙️" },
            ].map(({ href, label, accent, icon }) => (
              <Link key={href} href={href}>
                <div className={`border-4 border-neo-black ${accent} shadow-neo-sm hover:-translate-y-1 hover:shadow-neo-md transition-all duration-150 active:translate-x-1 active:translate-y-1 active:shadow-none p-4 text-center space-y-2 cursor-pointer`}>
                  <div className="text-3xl">{icon}</div>
                  <p className="font-black uppercase text-xs tracking-widest">{label}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
