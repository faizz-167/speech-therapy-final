"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";
import Link from "next/link";

interface Dashboard { total_patients: number; approved_patients: number; pending_patients: number; }

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Dashboard>("/therapist/dashboard").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBanner message={error} />;
  if (!data) return <SkeletonList count={3} />;

  return (
    <div className="space-y-6 animate-fade-up">
      <h1 className="text-3xl font-black uppercase">Dashboard</h1>
      <div className="grid grid-cols-3 gap-4">
        <NeoCard accent="secondary" className="text-center">
          <div className="text-4xl font-black">{data.total_patients}</div>
          <div className="font-bold uppercase text-sm">Total Patients</div>
        </NeoCard>
        <NeoCard accent="default" className="text-center">
          <div className="text-4xl font-black">{data.approved_patients}</div>
          <div className="font-bold uppercase text-sm">Approved</div>
        </NeoCard>
        <NeoCard accent="muted" className="text-center">
          <div className="text-4xl font-black">{data.pending_patients}</div>
          <div className="font-bold uppercase text-sm">Pending Approval</div>
        </NeoCard>
      </div>
      {data.pending_patients > 0 && (
        <NeoCard accent="accent" className="flex items-center justify-between">
          <span className="font-black">{data.pending_patients} patient(s) awaiting approval</span>
          <Link href="/therapist/patients"><NeoButton size="sm" variant="ghost">Review</NeoButton></Link>
        </NeoCard>
      )}
    </div>
  );
}
