"use client";

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import { useToast } from "../components/Toast";
import { Card, Header, RelativeTime, SeverityBadge, Stat } from "../components/ui";
import { api, type Incident, type MemoryDocument } from "../lib/api";

type Stats = {
  total_incidents: number;
  resolved_incidents: number;
  memory_count: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  avg_resolution_minutes: number | null;
  avg_resolution_by_category: Record<string, number>;
  resolution_time_improvement_pct: number | null;
  memory_utilization_rate: number;
  avg_memories_per_analysis: number;
  learning_curve: { n: number; title: string; memories_recalled: number; analysis_ms: number | null }[];
  top_recalled: { id: string; title: string; memories_recalled: number }[];
};

type Timeline = { timeline: { n: number; incident_id: string; title: string; category: string; at: string; lesson: string }[] };

export default function Dashboard() {
  const toast = useToast();
  const [stats, setStats] = useState<Stats | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [timeline, setTimeline] = useState<Timeline["timeline"]>([]);
  const [memories, setMemories] = useState<MemoryDocument[]>([]);
  const [memoriesLoading, setMemoriesLoading] = useState(true);
  const [memoryLoadError, setMemoryLoadError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<Stats>("/stats"),
      api<{ incidents: Incident[] }>("/incidents/history"),
      api<Timeline>("/memory/timeline"),
    ])
      .then(([s, h, t]) => { setStats(s); setIncidents(h.incidents); setTimeline(t.timeline); })
      .catch((e) => toast("error", e instanceof Error ? e.message : "Unable to load dashboard."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api<{ memories: MemoryDocument[] }>("/memory/documents")
      .then((result) => setMemories(result.memories))
      .catch((e) => setMemoryLoadError(e instanceof Error ? e.message : "Unable to load Hindsight memory provenance."))
      .finally(() => setMemoriesLoading(false));
  }, []);

  const curve = stats?.learning_curve ?? [];
  const trustedMemories = memories.filter((memory) => memory.trust_tier === "analyst-confirmed");
  const knownTimelineIds = new Set(timeline.map((item) => item.incident_id));
  const untrackedTimeline = trustedMemories.flatMap((memory) => {
    const incidentId = memory.tags.find((tag) => tag.startsWith("incident:"))?.slice("incident:".length) ?? memory.document_id;
    if (knownTimelineIds.has(incidentId)) return [];
    const incident = incidents.find((item) => item.id === incidentId);
    const category = memory.tags.find((tag) => tag.startsWith("category:") || tag.startsWith("type:"));
    return [{
      n: 0,
      incident_id: incidentId,
      title: incident?.title ?? incidentId,
      category: incident?.category ?? category?.slice(category.indexOf(":") + 1) ?? "Incident",
      at: memory.created_at ?? "",
      lesson: incident?.analyst_feedback ?? "",
    }];
  });
  const visibleTimeline = [...timeline, ...untrackedTimeline]
    .sort((left, right) => left.at.localeCompare(right.at))
    .map((item, index) => ({ ...item, n: index + 1 }));
  const maxRecalled = Math.max(1, ...curve.map((c) => c.memories_recalled));
  const cats = Object.entries(stats?.by_category ?? {});
  const maxCat = Math.max(1, ...cats.map(([, v]) => v));
  const firstTime = curve.find((c) => c.memories_recalled === 0);
  const latest = curve[curve.length - 1];
  const firstTimed = curve.find((item) => item.analysis_ms !== null);
  const latestTimed = [...curve].reverse().find((item) => item.analysis_ms !== null);
  const measuredSpeedup = firstTimed && latestTimed && firstTimed.analysis_ms! > latestTimed.analysis_ms!
    ? Math.round(firstTimed.analysis_ms! / Math.max(1, latestTimed.analysis_ms!) * 10) / 10
    : null;

  const revokeMemory = async (memory: MemoryDocument) => {
    if (!window.confirm(`Permanently revoke ${memory.document_id} from Hindsight?`)) return;
    setRevoking(memory.document_id);
    try {
      await api(`/memory/documents/${encodeURIComponent(memory.document_id)}`, { method: "DELETE" });
      setMemories((current) => current.filter((item) => item.document_id !== memory.document_id));
      const incidentId = memory.tags.find((tag) => tag.startsWith("incident:"))?.slice("incident:".length);
      setIncidents((current) => current.map((item) => item.id === incidentId ? { ...item, memory_revoked: true } : item));
      setTimeline((current) => current.filter((item) => item.incident_id !== incidentId));
      toast("success", "Memory revoked; future trusted recall will no longer use it.");
      const refreshed = await api<Stats>("/stats");
      setStats(refreshed);
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Unable to revoke memory.");
    } finally {
      setRevoking(null);
    }
  };

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <Header active="dashboard" memoryCount={memoriesLoading || memoryLoadError ? undefined : trustedMemories.length} />

        {loading ? (
          <div className="space-y-6">
            <div className="skeleton h-44 rounded-[28px]" />
            <div className="grid gap-4 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-28" />)}</div>
            <div className="skeleton h-64 rounded-2xl" />
          </div>
        ) : !stats ? (
          <Card className="border-amber-400/20">
            <p className="section-kicker text-amber-200">CONNECTION ISSUE</p>
            <p className="mt-2 text-lg font-medium text-white">Dashboard data could not be loaded.</p>
            <p className="mt-1 text-sm text-slate-400">Check that the backend is running and connected, then refresh this page.</p>
            <button onClick={() => window.location.reload()} className="mt-4 rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/5">Retry</button>
          </Card>
        ) : (
          <div className="fade-up space-y-6">
            <section className="hero-panel grid gap-6 rounded-[28px] p-6 sm:p-8 lg:grid-cols-[1fr_auto] lg:items-end">
              <div className="relative z-10">
                <p className="eyebrow">SOC PERFORMANCE · LIVE LEARNING</p>
                <h2 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">The memory behind every response.</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">Follow incident trends, inspect which trusted sources informed analysis, and revoke memories that should no longer influence the agent.</p>
              </div>
              <div className="relative z-10 flex flex-wrap gap-2">
                <Link href="/" className="btn-primary rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition">Analyze an incident →</Link>
                <span className="inline-flex items-center rounded-xl border border-white/10 bg-slate-950/35 px-4 py-2.5 text-xs text-slate-300">{memoriesLoading ? "Loading…" : trustedMemories.length} trusted memories</span>
              </div>
            </section>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Stat label="Incidents analyzed" value={stats.total_incidents} sub={`${stats.resolved_incidents} resolved`} accent="text-cyan-300" />
              <Stat label="Memories retained" value={memoriesLoading || memoryLoadError ? "—" : memories.length} sub={memoryLoadError ? "Hindsight registry unavailable" : `in Hindsight · ${trustedMemories.length} analyst-confirmed`} accent="text-purple-300" />
              <Stat label="Memory utilization" value={`${stats.memory_utilization_rate}%`} sub={`${stats.avg_memories_per_analysis} recalled / analysis`} accent="text-emerald-300" />
              <Stat
                label="Avg resolution"
                value={stats.avg_resolution_minutes !== null ? `${stats.avg_resolution_minutes}m` : "—"}
                sub={stats.resolution_time_improvement_pct !== null ? `${stats.resolution_time_improvement_pct >= 0 ? "▼" : "▲"} ${Math.abs(stats.resolution_time_improvement_pct)}% vs. earlier half` : "needs more resolved incidents"}
                accent="text-yellow-200"
              />
            </div>

            {/* LEARNING CURVE */}
            <Card className="!p-5 sm:!p-7">
              <p className="section-kicker">RECALL OVER TIME</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight">Learning curve</h2>
              <p className="mt-1 text-sm text-slate-400">Trusted memories recalled for each analysis, oldest to newest.</p>
              {firstTime && latest && curve.length > 1 && (
                <p className="mt-3 rounded-lg bg-purple-500/10 px-4 py-2 text-sm text-purple-200">
                  First incident: <b>{firstTime.memories_recalled} memories</b> → latest: <b>{latest.memories_recalled} memories</b> used.
                </p>
              )}
              {firstTimed && latestTimed && firstTimed !== latestTimed && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-700/70 bg-slate-950/50 p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-500">First measured analysis</p>
                    <p className="mt-1 text-2xl font-bold text-slate-200">{(firstTimed.analysis_ms! / 1000).toFixed(1)}s</p>
                    <p className="mt-1 truncate text-xs text-slate-400">{firstTimed.title} · {firstTimed.memories_recalled} memories</p>
                  </div>
                  <div className="rounded-xl border border-cyan-800/50 bg-cyan-950/20 p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-500">Latest measured analysis</p>
                    <p className="mt-1 text-2xl font-bold text-cyan-200">{(latestTimed.analysis_ms! / 1000).toFixed(1)}s</p>
                    <p className="mt-1 truncate text-xs text-slate-400">{latestTimed.title} · {latestTimed.memories_recalled} memories</p>
                  </div>
                  <p className="text-xs text-slate-500 sm:col-span-2">
                    {measuredSpeedup
                      ? `Measured ${measuredSpeedup}× faster from first to latest analysis.`
                      : "Latest analysis was not faster than the first. These are observed wall-clock times, not a controlled benchmark."}
                    {" "}Memory retrieval and model/network latency vary by incident and service load.
                  </p>
                </div>
              )}
              {curve.length === 0 ? (
                <div className="mt-5 rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 px-5 py-8 text-center">
                  <p className="text-sm font-medium text-slate-200">Your learning curve starts with the first case.</p>
                  <p className="mt-1 text-xs text-slate-500">Analyze an incident, resolve it, and record analyst feedback to build trusted memory.</p>
                  <Link href="/" className="mt-4 inline-flex rounded-lg border border-teal-300/20 bg-teal-300/[0.06] px-4 py-2 text-xs font-medium text-teal-100 hover:bg-teal-300/10">Go to incident analysis</Link>
                </div>
              ) : (
                <div className="mt-6 flex h-40 items-end gap-2 overflow-x-auto">
                  {curve.map((c) => (
                    <div key={c.n} className="group flex min-w-[28px] flex-1 flex-col items-center justify-end" title={`${c.title}: ${c.memories_recalled} memories`}>
                      <span className="mb-1 text-[10px] text-slate-400">{c.memories_recalled}</span>
                      <div className="w-full rounded-t-md bg-gradient-to-t from-purple-600 to-cyan-400 transition group-hover:brightness-125"
                        style={{ height: `${Math.max(4, (c.memories_recalled / maxRecalled) * 100)}%` }} />
                      <span className="mt-1 text-[10px] text-slate-500">#{c.n}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <div className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <h2 className="text-xl font-semibold">Most common incident types</h2>
                <div className="mt-4 space-y-3">
                  {cats.length === 0 && <p className="text-slate-500">No data yet.</p>}
                  {cats.map(([name, n]) => (
                    <div key={name}>
                      <div className="mb-1 flex justify-between text-sm"><span>{name}</span><span className="text-slate-400">{n}{stats.avg_resolution_by_category[name] ? ` · avg ${stats.avg_resolution_by_category[name]}m` : ""}</span></div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500" style={{ width: `${(n / maxCat) * 100}%` }} /></div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <h2 className="text-xl font-semibold">Top recalled incidents</h2>
                <ol className="mt-4 space-y-3">
                  {stats.top_recalled.length === 0 && <p className="text-slate-500">No data yet.</p>}
                  {stats.top_recalled.map((t, i) => (
                    <li key={t.id} className="flex min-w-0 items-center justify-between gap-3 rounded-lg bg-slate-950/50 px-3 py-2 text-sm">
                      <span className="min-w-0 truncate"><span className="mr-2 text-slate-500">{i + 1}.</span>{t.title}</span>
                      <span className="shrink-0 rounded-full bg-purple-500/20 px-2 py-0.5 text-xs text-purple-200">{t.memories_recalled} memories</span>
                    </li>
                  ))}
                </ol>
              </Card>
            </div>

            <Card className="!p-5 sm:!p-7">
              <p className="section-kicker">AUDIT &amp; CONTROL</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight">Memory provenance</h2>
              <p className="mt-1 text-sm text-slate-400">Blame view: these source documents can influence trusted recall only when analyst-confirmed. Raw telemetry is retained with a lower trust tier and excluded from Vigil&apos;s recall.</p>
              {memoryLoadError ? (
                <p className="mt-4 rounded-lg border border-amber-800/50 bg-amber-950/30 p-3 text-sm text-amber-200">{memoryLoadError}</p>
              ) : memories.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">No application memories are currently registered in Hindsight.</p>
              ) : (
                <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
                  {memories.map((memory, index) => {
                    const incidentTag = memory.tags.find((tag) => tag.startsWith("incident:"));
                    const trusted = memory.trust_tier === "analyst-confirmed";
                    return (
                      <div key={`${memory.document_id}-${index}`} className="rounded-xl border border-slate-700/70 bg-slate-950/50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-mono text-xs text-slate-300">{incidentTag?.slice("incident:".length) ?? memory.document_id}</p>
                            {incidentTag && incidents.find((incident) => incident.id === incidentTag.slice("incident:".length)) && (
                              <p className="mt-1 text-xs text-slate-400">{incidents.find((incident) => incident.id === incidentTag.slice("incident:".length))?.title}</p>
                            )}
                            <p className={`mt-1 text-xs font-semibold ${trusted ? "text-emerald-300" : "text-amber-300"}`}>Trust tier: {memory.trust_tier}</p>
                          </div>
                          <button onClick={() => revokeMemory(memory)} disabled={revoking === memory.document_id} className="rounded-lg border border-red-800/70 px-3 py-1.5 text-xs text-red-300 hover:bg-red-950/40 disabled:opacity-50">
                            {revoking === memory.document_id ? "Revoking…" : "Revoke memory"}
                          </button>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {memory.tags.map((tag, tagIndex) => <span key={`${tag}-${tagIndex}`} className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">{tag}</span>)}
                        </div>
                        <p className="mt-2 text-[10px] text-slate-500">{memory.text_length ?? "?"} characters · {memory.created_at ? <RelativeTime iso={memory.created_at} /> : "creation time unavailable"}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            {/* MEMORY TIMELINE */}
            <Card className="!p-5 sm:!p-7">
              <p className="section-kicker">ANALYST-CONFIRMED KNOWLEDGE</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight">Memory timeline</h2>
              <p className="mt-1 text-sm text-slate-400">How the agent&apos;s knowledge grew, one lesson at a time.</p>
              {visibleTimeline.length === 0 ? <p className="mt-4 text-slate-500">{memoriesLoading ? "Loading trusted memory timeline…" : "No memories yet."}</p> : (
                <ol className="relative mt-5 space-y-5 border-l border-purple-500/40 pl-6">
                  {visibleTimeline.map((t, index) => (
                    <li key={`${t.incident_id}-${index}`} className="relative">
                      <span className="absolute -left-[33px] flex h-6 w-6 items-center justify-center rounded-full bg-purple-600 text-[11px] font-bold">{t.n}</span>
                      <p className="text-sm font-medium">{t.title} <span className="ml-2 text-xs text-slate-500">{t.category} · <RelativeTime iso={t.at} /></span></p>
                      {t.lesson && <p className="mt-1 text-sm text-slate-400">“{t.lesson}{t.lesson.length >= 160 ? "…" : ""}”</p>}
                    </li>
                  ))}
                </ol>
              )}
            </Card>

            {/* HISTORY TABLE */}
            <Card className="!p-5 sm:!p-7">
              <p className="section-kicker">CASE RECORDS</p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight">Incident history</h2>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="text-xs uppercase tracking-wider text-slate-500">
                    <tr><th className="pb-3">Incident</th><th className="pb-3">Severity</th><th className="pb-3">Status</th><th className="pb-3">Memories recalled</th><th className="pb-3">Resolved in</th><th className="pb-3">When</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {incidents.map((i) => (
                      <Fragment key={i.id}>
                      <tr>
                        <td className="py-3 pr-4"><p className="font-medium text-slate-200">{i.title}</p><p className="font-mono text-[11px] text-slate-500">{i.id}{i.seeded ? " · seeded" : ""}{i.memory_revoked ? " · memory revoked" : ""}</p></td>
                        <td className="py-3 pr-4"><SeverityBadge severity={i.severity} /></td>
                        <td className="py-3 pr-4"><span className={i.status === "resolved" ? "text-emerald-300" : "text-yellow-300"}>{i.status}</span></td>
                        <td className="py-3 pr-4">{i.seeded ? "—" : i.memories_recalled ?? "—"}</td>
                        <td className="py-3 pr-4">{i.resolution_minutes != null ? `${i.resolution_minutes}m` : "—"}</td>
                        <td className="py-3 text-slate-500"><RelativeTime iso={i.created_at} /></td>
                      </tr>
                      {i.memory_details && i.memory_details.length > 0 && (
                        <tr key={`${i.id}-memory-trace`} className="bg-slate-950/30">
                          <td colSpan={6} className="px-4 py-2 text-xs text-slate-400">
                            Decision memory sources: {i.memory_details.map((memory, index) => (
                              <span key={`${memory.document_id ?? "memory"}-${index}`} className="mr-2 inline-flex rounded bg-purple-500/10 px-2 py-1 font-mono text-[10px] text-purple-200">
                                {memory.document_id ?? memory.tags.find((tag) => tag.startsWith("incident:"))?.slice("incident:".length) ?? `memory ${index + 1}`}
                              </span>
                            ))}
                          </td>
                        </tr>
                      )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
                {incidents.length === 0 && <p className="py-6 text-center text-slate-500">No incidents yet — analyze one or seed demo data.</p>}
              </div>
            </Card>
          </div>
        )}
      </div>
    </main>
  );
}
