"use client";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Patient } from "@/types";
import { PatientCard } from "@/components/therapist/PatientCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

type StatusFilter = "all" | "pending" | "approved";

export default function PatientsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const { data: patients, error, isLoading } = useQuery<Patient[]>({
    queryKey: ["therapist", "patients"],
    queryFn: () => api.get<Patient[]>("/therapist/patients"),
  });

  const filtered = useMemo(() => {
    if (!patients) return [];
    return patients.filter((p) => {
      const matchesSearch =
        p.full_name.toLowerCase().includes(search.toLowerCase()) ||
        p.email.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "all" || p.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [patients, search, statusFilter]);

  const counts = useMemo(() => ({
    all: patients?.length ?? 0,
    approved: patients?.filter((p) => p.status === "approved").length ?? 0,
    pending: patients?.filter((p) => p.status === "pending").length ?? 0,
  }), [patients]);

  if (isLoading) return <LoadingState label="Loading patients..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;

  const tabs: { key: StatusFilter; label: string; accent: string }[] = [
    { key: "all", label: "All", accent: "bg-neo-black text-white" },
    { key: "approved", label: "Approved", accent: "bg-neo-secondary text-neo-black" },
    { key: "pending", label: "Pending", accent: "bg-neo-muted text-neo-black" },
  ];

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-7xl mx-auto space-y-8">

      {/* ── HEADER ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-8 border-neo-black pb-6">
        <div>
          <div className="inline-block bg-neo-muted border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-sm mb-3 rotate-1 shadow-neo-sm">
            Patient Registry
          </div>
          <h1 className="text-5xl md:text-6xl font-black uppercase tracking-tighter leading-none">
            Patients
          </h1>
        </div>
        <div className="mt-4 md:mt-0 font-black text-lg border-4 border-neo-black px-4 py-2 bg-white shadow-neo-sm">
          {counts.all} total
        </div>
      </div>

      {/* ── SEARCH + FILTER ── */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="flex-1 relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 font-black text-neo-black/40 text-lg pointer-events-none">⌕</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email..."
            className="w-full border-4 border-neo-black bg-white px-10 py-3 font-bold text-base focus:outline-none focus:bg-neo-secondary focus:shadow-neo-sm placeholder:text-neo-black/30 transition-all"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 font-black text-neo-black/40 hover:text-neo-black text-lg"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* ── STATUS TABS ── */}
      <div className="flex flex-wrap gap-2">
        {tabs.map(({ key, label, accent }) => (
          <button
            key={key}
            onClick={() => setStatusFilter(key)}
            className={`border-4 border-neo-black px-4 py-2 font-black uppercase tracking-widest text-sm transition-all duration-100 ${
              statusFilter === key
                ? `${accent} shadow-neo-sm -translate-y-0.5`
                : "bg-white text-neo-black hover:bg-neo-bg"
            }`}
          >
            {label}
            <span className="ml-2 opacity-70">({counts[key]})</span>
          </button>
        ))}
      </div>

      {/* ── PATIENT GRID ── */}
      {!patients || patients.length === 0 ? (
        <EmptyState
          icon="🧑‍⚕️"
          heading="No Patients Yet"
          subtext="Share your therapist code for patients to register."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="🔍"
          heading="No Matches"
          subtext={`No patients match "${search}" with filter "${statusFilter}".`}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((p, i) => (
            <div key={p.patient_id} className={`stagger-${Math.min(i + 1, 6)}`}>
              <PatientCard patient={p} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
