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
    <div className="space-y-10 animate-fade-up p-4 md:p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-end border-b-8 border-neo-black pb-6 mb-8">
        <div>
           <div className="inline-block bg-neo-accent border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-sm mb-4 -rotate-2 shadow-neo-sm">Control Center</div>
           <h1 className="text-6xl font-black uppercase tracking-tighter text-white text-stroke-black drop-shadow-[4px_4px_0_rgba(0,0,0,1)]">Dashboard</h1>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <NeoCard accent="secondary" className="text-center py-12 relative overflow-hidden group hover:-translate-y-2 transition-transform">
          <div className="absolute -right-6 -top-6 w-32 h-32 bg-white border-8 border-neo-black rounded-full mix-blend-overlay group-hover:scale-150 transition-transform duration-500"></div>
          <div className="text-8xl font-black relative z-10 drop-shadow-[4px_4px_0_rgba(255,255,255,1)]">{data.total_patients}</div>
          <div className="font-black uppercase tracking-widest mt-6 bg-neo-black text-white inline-block px-5 py-2 border-2 border-white relative z-10">Total Patients</div>
        </NeoCard>
        
        <NeoCard accent="default" className="text-center py-12 relative overflow-hidden group hover:-translate-y-2 transition-transform">
          <div className="absolute -left-6 -bottom-6 w-32 h-32 bg-neo-primary border-8 border-neo-black rounded-none mix-blend-overlay group-hover:rotate-45 transition-transform duration-500"></div>
          <div className="text-8xl font-black relative z-10 drop-shadow-[4px_4px_0_rgba(0,0,0,1)] text-white">{data.approved_patients}</div>
          <div className="font-black uppercase tracking-widest mt-6 bg-white text-neo-black inline-block px-5 py-2 border-4 border-neo-black relative z-10 shadow-neo-sm">Approved</div>
        </NeoCard>
        
        <NeoCard accent="muted" className="text-center py-12 relative overflow-hidden group hover:-translate-y-2 transition-transform">
          <div className="text-8xl font-black relative z-10 text-neo-black">{data.pending_patients}</div>
          <div className="font-black uppercase tracking-widest mt-6 bg-neo-warning text-neo-black inline-block px-5 py-2 border-4 border-neo-black relative z-10 shadow-neo-sm">Pending Appr.</div>
        </NeoCard>
      </div>

      {data.pending_patients > 0 && (
        <div className="mt-16 relative">
          <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-neo-black text-white px-6 py-2 font-black uppercase tracking-widest text-sm border-4 border-neo-black z-20 shadow-neo-sm">Action Required</div>
          <NeoCard accent="accent" className="flex flex-col md:flex-row items-center justify-between p-10 border-8 relative z-10 mt-8">
            <div className="flex items-center gap-6">
               <div className="w-16 h-16 bg-white border-4 border-neo-black flex items-center justify-center text-4xl shadow-neo-sm rounded-none">⚠️</div>
               <span className="font-black text-3xl uppercase tracking-tighter leading-none">{data.pending_patients} PATIENT(S)<br/>AWAITING APPROVAL</span>
            </div>
            <Link href="/therapist/patients" className="w-full md:w-auto mt-8 md:mt-0">
               <NeoButton size="lg" className="w-full md:w-auto text-2xl py-6 px-12 bg-white text-neo-black border-4 shadow-neo-md hover:bg-neo-black hover:text-white transition-colors duration-150">REVIEW NOW</NeoButton>
            </Link>
          </NeoCard>
        </div>
      )}
    </div>
  );
}
