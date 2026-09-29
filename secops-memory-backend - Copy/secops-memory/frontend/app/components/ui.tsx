"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Severity } from "../lib/api";
import { API } from "../lib/api";

const sev: Record<Severity, string> = {
  Critical: "border-red-500/50 bg-red-500/15 text-red-300",
  High: "border-orange-500/50 bg-orange-500/15 text-orange-300",
  Medium: "border-yellow-500/50 bg-yellow-500/15 text-yellow-200",
  Low: "border-emerald-500/50 bg-emerald-500/15 text-emerald-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${sev[severity] ?? sev.Medium}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {severity}
    </span>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`glass rounded-2xl p-6 ${className}`}>{children}</section>;
}

export function Stat({ label, value, sub, accent = "text-white" }: { label: string; value: React.ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="glass group overflow-hidden rounded-2xl p-5 transition duration-200 hover:-translate-y-0.5">
      <div className="mb-4 flex items-center justify-between">
        <p className="section-kicker">{label}</p>
        <span className="h-1.5 w-8 rounded-full bg-gradient-to-r from-teal-400/80 to-blue-400/70 transition-all group-hover:w-12" />
      </div>
      <p className={`text-3xl font-semibold tracking-tight ${accent}`}>{value}</p>
      {sub && <p className="mt-2 text-xs leading-5 text-slate-500">{sub}</p>}
    </div>
  );
}

export function Header({ active, memoryCount }: { active: "analyze" | "dashboard"; memoryCount?: number }) {
  const [hindsightConnected, setHindsightConnected] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API}/health`, { cache: "no-store" });
        if (!response.ok) throw new Error(`Health request failed (${response.status})`);
        const health = await response.json() as { hindsight_reachable?: boolean };
        if (active) setHindsightConnected(health.hindsight_reachable === true);
      } catch {
        if (active) setHindsightConnected(false);
      }
    };
    void checkHealth();
    const interval = window.setInterval(checkHealth, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const tab = (on: boolean) =>
    `rounded-lg px-4 py-2 text-sm font-medium transition ${on ? "bg-teal-300/10 text-teal-200 ring-1 ring-teal-300/15" : "text-slate-400 hover:bg-white/5 hover:text-white"}`;
  return (
    <header className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.07] pb-5">
      <div className="flex items-center gap-3">
        <div className="shield-glow flex h-12 w-12 items-center justify-center rounded-2xl border border-teal-200/20 bg-gradient-to-br from-teal-400/20 to-blue-500/15 text-teal-100">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-6 w-6">
            <path d="M12 3 20 6v5c0 5.2-3.4 8.4-8 10-4.6-1.6-8-4.8-8-10V6l8-3Z" stroke="currentColor" strokeWidth="1.6" />
            <path d="m8.5 12 2.2 2.2 4.8-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Vigil <span className="font-normal text-slate-500">/</span> <span className="text-slate-300">SecOps Memory</span></h1>
          <p className="mt-0.5 text-xs tracking-wide text-slate-500">
            TRUST-GATED INCIDENT RESPONSE
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[11px] font-medium ${
            hindsightConnected === true
              ? "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-200"
              : hindsightConnected === false
                ? "border-amber-400/20 bg-amber-400/[0.07] text-amber-200"
                : "border-slate-500/20 bg-slate-500/[0.07] text-slate-300"
          }`}
          title={hindsightConnected === true ? "Hindsight is reachable" : hindsightConnected === false ? "Hindsight is not reachable" : "Checking Hindsight connection"}
          aria-live="polite"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${hindsightConnected === true ? "bg-emerald-300" : hindsightConnected === false ? "bg-amber-300" : "bg-slate-400"}`} />
          {hindsightConnected === true ? "Memory online" : hindsightConnected === false ? "Memory offline" : "Checking memory"}
        </span>
        {memoryCount !== undefined && (
          <span className="rounded-full border border-violet-300/15 bg-violet-300/[0.07] px-3 py-2 text-[11px] font-medium text-violet-100">
            {memoryCount} memories
          </span>
        )}
        <nav aria-label="Main navigation" className="flex items-center gap-1 rounded-xl border border-white/[0.07] bg-slate-950/40 p-1">
          <Link href="/" className={tab(active === "analyze")}>Analyze</Link>
          <Link href="/dashboard" className={tab(active === "dashboard")}>Dashboard</Link>
        </nav>
      </div>
    </header>
  );
}

export function timeAgo(iso?: string) {
  if (!iso) return "";
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "Unknown time";
  const s = (Date.now() - timestamp) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function RelativeTime({ iso, className }: { iso?: string; className?: string }) {
  const [label, setLabel] = useState(() => {
    if (!iso) return "";
    const timestamp = new Date(iso);
    return Number.isNaN(timestamp.getTime())
      ? "Unknown time"
      : timestamp.toISOString().slice(0, 10);
  });

  useEffect(() => {
    if (!iso) return;
    const update = () => setLabel(timeAgo(iso));
    update();
    const interval = window.setInterval(update, 60000);
    return () => window.clearInterval(interval);
  }, [iso]);

  return <time dateTime={iso} className={className}>{label}</time>;
}
