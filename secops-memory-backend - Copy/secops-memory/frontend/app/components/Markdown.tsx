import React from "react";

/* Small dependency-free markdown renderer (headings, bold, code, lists, paragraphs).
   Sections whose heading mentions "historical"/"memory"/"lesson" are highlighted as
   coming from Hindsight memory. */

function inline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i} className="font-semibold text-white">{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i} className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[0.85em] text-cyan-300">{p.slice(1, -1)}</code>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
}

type Block = { heading?: string; nodes: React.ReactNode[] };

export default function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const blocks: Block[] = [{ nodes: [] }];
  let list: string[] = [];
  let ordered = false;
  let k = 0;
  const cur = () => blocks[blocks.length - 1];

  const flushList = () => {
    if (!list.length) return;
    const items = list.map((l, i) => <li key={i}>{inline(l)}</li>);
    cur().nodes.push(
      ordered
        ? <ol key={k++} className="ml-5 list-decimal space-y-1.5 marker:text-cyan-400">{items}</ol>
        : <ul key={k++} className="ml-5 list-disc space-y-1.5 marker:text-cyan-400">{items}</ul>
    );
    list = [];
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^#{1,6}\s+(.*)$/) || line.match(/^\*\*(\d+\.\s.*?)\*\*:?$/);
    const ul = line.match(/^\s*[-*•]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (h) {
      flushList();
      blocks.push({ heading: h[1].replace(/\*\*/g, ""), nodes: [] });
    } else if (ul || ol) {
      const isOrdered = !!ol && !ul;
      if (list.length && ordered !== isOrdered) flushList();
      ordered = isOrdered;
      list.push((ul || ol)![1]);
    } else if (line.trim() === "" || /^-{3,}$/.test(line)) {
      flushList();
    } else if (line.startsWith("|")) {
      flushList();
      if (!/^\|[\s:-|]+\|?$/.test(line))
        cur().nodes.push(<p key={k++} className="font-mono text-xs text-slate-400">{line}</p>);
    } else {
      flushList();
      cur().nodes.push(<p key={k++}>{inline(line)}</p>);
    }
  }
  flushList();

  return (
    <div className="space-y-4 text-sm leading-7 text-slate-300">
      {blocks.map((b, i) => {
        const fromMemory = b.heading && /histor|memory|lesson/i.test(b.heading);
        return (
          <div
            key={i}
            className={fromMemory ? "rounded-xl border border-purple-500/40 bg-purple-500/10 p-4" : ""}
          >
            {b.heading && (
              <h3 className="mb-2 flex items-center gap-2 text-base font-semibold text-white">
                {b.heading}
                {fromMemory && (
                  <span className="rounded-full bg-purple-500/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-200">
                    🧠 from memory
                  </span>
                )}
              </h3>
            )}
            <div className="space-y-2">{b.nodes}</div>
          </div>
        );
      })}
    </div>
  );
}
