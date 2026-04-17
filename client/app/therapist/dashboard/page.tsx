"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import Link from "next/link";
import { TherapistDashboard } from "@/types";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Cell,
} from "recharts";

function StatCard({ value, label, accent, delay = "stagger-1" }: {
  value: number | string; label: string; accent: string; delay?: string;
}) {
  return (
    <div className={`border-4 border-neo-black ${accent} shadow-neo-md hover:-translate-y-1 hover:-translate-x-1 hover:shadow-neo-lg transition-all duration-200 cursor-default ${delay}`}>
      <div className="p-6 text-center space-y-2">
        <div className="text-7xl font-black leading-none">{value}</div>
        <div className="font-black uppercase tracking-widest text-sm border-t-4 border-neo-black pt-3 mt-3">{label}</div>
      </div>
    </div>
  );
}

function NeoTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-4 border-neo-black bg-white shadow-neo-sm p-3 font-black text-sm">
      <p className="uppercase tracking-widest text-xs text-neo-black/60 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="uppercase">{p.name}: <span className="text-neo-accent">{p.value}</span></p>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const { data, error, isLoading } = useQuery<TherapistDashboard>({
    queryKey: ["therapist", "dashboard"],
    queryFn: () => api.get<TherapistDashboard>("/therapist/dashboard"),
  });

  if (isLoading) return <LoadingState label="Loading dashboard..." />;
  if (error) return <ErrorState message={error instanceof Error ? error.message : "Failed to load"} />;
  if (!data) return <LoadingState label="Loading dashboard..." />;

  const operationalData = [
    { name: "Pending\nApproval", value: data.pending_patients, fill: "#C4B5FD" },
    { name: "No\nBaseline", value: data.patients_without_baseline, fill: "#FFD93D" },
    { name: "No\nPlan", value: data.patients_without_approved_plan, fill: "#FF6B6B" },
    { name: "Plan\nPending", value: data.plans_pending_approval, fill: "#FF6B6B" },
  ];

  const radarData = [
    { metric: "Approved", value: data.total_patients > 0 ? Math.round((data.approved_patients / data.total_patients) * 100) : 0 },
    { metric: "Baseline", value: data.total_patients > 0 ? Math.round(((data.total_patients - data.patients_without_baseline) / data.total_patients) * 100) : 0 },
    { metric: "Has Plan", value: data.total_patients > 0 ? Math.round(((data.total_patients - data.patients_without_approved_plan) / data.total_patients) * 100) : 0 },
    { metric: "Active", value: data.total_patients > 0 ? Math.round((data.approved_patients / data.total_patients) * 100) : 0 },
    { metric: "Pending", value: data.total_patients > 0 ? Math.round((data.pending_patients / data.total_patients) * 100) : 0 },
  ];

  return (
    <div className="animate-fade-up p-4 md:p-8 max-w-7xl mx-auto space-y-10">

      {/* ── PAGE HEADER ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-8 border-neo-black pb-6">
        <div>
          <div className="inline-block bg-neo-accent border-4 border-neo-black px-4 py-1 font-black uppercase tracking-widest text-sm mb-4 -rotate-2 shadow-neo-sm">
            Control Center
          </div>
          <h1 className="text-5xl md:text-7xl font-black uppercase tracking-tighter leading-none">
            Dashboard
          </h1>
        </div>
        <Link href="/therapist/patients">
          <button className="border-4 border-neo-black bg-neo-secondary px-6 py-3 font-black uppercase tracking-widest text-sm shadow-neo-sm hover:-translate-y-1 hover:shadow-neo-md transition-all duration-150 active:translate-x-1 active:translate-y-1 active:shadow-none mt-4 md:mt-0">
            View All Patients →
          </button>
        </Link>
      </div>

      {/* ── STAT CARDS ── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <StatCard value={data.total_patients} label="Total Patients" accent="bg-neo-secondary" delay="stagger-1" />
        <StatCard value={data.approved_patients} label="Approved" accent="bg-white" delay="stagger-2" />
        <StatCard value={data.pending_patients} label="Pending Approval" accent="bg-neo-muted" delay="stagger-3" />
      </div>

      {/* ── ACTION REQUIRED BANNER ── */}
      {data.pending_patients > 0 && (
        <div className="relative stagger-4">
          <div className="absolute -top-4 left-8 bg-neo-black text-white px-4 py-1 font-black uppercase tracking-widest text-xs border-4 border-neo-black z-20">
            Action Required
          </div>
          <div className="border-8 border-neo-black bg-neo-accent shadow-neo-lg p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mt-4">
            <div className="flex items-center gap-5">
              <div className="w-14 h-14 bg-white border-4 border-neo-black flex items-center justify-center text-3xl shadow-neo-sm font-black shrink-0">!</div>
              <div>
                <p className="font-black text-3xl uppercase tracking-tighter leading-none">
                  {data.pending_patients} PATIENT{data.pending_patients !== 1 ? "S" : ""} AWAITING APPROVAL
                </p>
                <p className="font-bold text-sm mt-1">Review and approve to unlock their therapy plans.</p>
              </div>
            </div>
            <Link href="/therapist/patients" className="w-full sm:w-auto shrink-0">
              <button className="w-full border-4 border-neo-black bg-white px-8 py-3 font-black uppercase tracking-widest text-base shadow-neo-sm hover:bg-neo-black hover:text-white transition-colors duration-150 active:translate-x-1 active:translate-y-1 active:shadow-none">
                REVIEW NOW →
              </button>
            </Link>
          </div>
        </div>
      )}

      {/* ── CHARTS ROW ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Bar chart — operational overview */}
        <div className="border-4 border-neo-black bg-white shadow-neo-md stagger-4">
          <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center gap-2">
            <span className="w-3 h-3 bg-neo-secondary inline-block border-2 border-white"></span>
            Operational Overview
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={operationalData} barSize={48}>
                <CartesianGrid strokeDasharray="0" stroke="#000" strokeWidth={1} opacity={0.08} vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fontWeight: 900, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fontWeight: 700, fontFamily: "Space Grotesk", fill: "#000" }} axisLine={{ stroke: "#000", strokeWidth: 2 }} tickLine={false} width={24} />
                <Tooltip content={<NeoTooltip />} cursor={{ fill: "rgba(0,0,0,0.05)" }} />
                <Bar dataKey="value" name="Count" stroke="#000" strokeWidth={2} radius={0}>
                  {operationalData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Radar chart — patient lifecycle */}
        <div className="border-4 border-neo-black bg-white shadow-neo-md stagger-5">
          <div className="bg-neo-black text-white px-5 py-3 font-black uppercase tracking-widest text-sm flex items-center gap-2">
            <span className="w-3 h-3 bg-neo-accent inline-block border-2 border-white"></span>
            Patient Lifecycle (%)
          </div>
          <div className="p-5">
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#000" strokeOpacity={0.15} />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fontWeight: 900, fontFamily: "Space Grotesk", fill: "#000" }} />
                <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="%" dataKey="value" stroke="#000" strokeWidth={2} fill="#FFD93D" fillOpacity={0.7} dot={{ fill: "#000", r: 3 }} />
                <Tooltip content={<NeoTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── QUICK ACTION GRID ── */}
      <div className="stagger-6">
        <h2 className="font-black uppercase tracking-widest text-base mb-4 border-b-4 border-neo-black pb-2">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Pending Approvals", count: data.pending_patients, accent: "bg-neo-muted", href: "/therapist/patients", cta: "Review" },
            { label: "Without Baseline", count: data.patients_without_baseline, accent: "bg-neo-secondary", href: "/therapist/patients", cta: "View" },
            { label: "No Approved Plan", count: data.patients_without_approved_plan, accent: "bg-neo-accent", href: "/therapist/patients", cta: "Generate" },
            { label: "Plans Pending Approval", count: data.plans_pending_approval, accent: "bg-white", href: "/therapist/patients", cta: "Approve" },
          ].map(({ label, count, accent, href, cta }) => (
            <div key={label} className={`border-4 border-neo-black ${accent} shadow-neo-sm hover:-translate-y-1 hover:shadow-neo-md transition-all duration-150 flex flex-col justify-between p-4`}>
              <div>
                <p className="font-black uppercase text-xs tracking-widest mb-2">{label}</p>
                <p className="text-5xl font-black leading-none">{count}</p>
              </div>
              <Link href={href} className="mt-4 block">
                <button className="w-full border-2 border-neo-black bg-neo-black text-white px-3 py-2 font-black uppercase tracking-widest text-xs hover:bg-white hover:text-neo-black transition-colors duration-150 active:translate-x-0.5 active:translate-y-0.5">
                  {cta} →
                </button>
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
