"use client";

import { useCurrentTime } from "@/hooks/useCurrentTime";

interface ActiveScan {
  scan_id: string;
  run_id: string;
  batches: string[];
  status: string;
  timestamp: number;
  estimated_duration: number;
}

interface ActiveScansDisplayProps {
  activeScans: ActiveScan[];
  refreshingId: string | null;
  onRefresh: (scanId: string) => Promise<void>;
  onCancel: (scanId: string) => Promise<void>;
  setRefreshingId: (id: string | null) => void;
}

export function ActiveScansDisplay({
  activeScans,
  refreshingId,
  onRefresh,
  onCancel,
  setRefreshingId,
}: ActiveScansDisplayProps) {
  const currentTime = useCurrentTime();

  return (
    <div className="space-y-3 mb-4">
      {activeScans.map((scan) => {
        const formattedDate = scan.timestamp > 0
          ? new Date(scan.timestamp * 1000).toLocaleString(undefined, {
            month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
          })
          : "Just now";

        const batchTitle = scan.batches.map(b => b === "all" ? "Master Scan" : b.charAt(0).toUpperCase() + b.slice(1).replace("_", " ")).join(", ");

        const statusColor = scan.status === "in_progress"
          ? "text-emerald-400 bg-emerald-950/40 border-emerald-500/20"
          : scan.status === "queued" || scan.status.startsWith("Starting") || scan.status.startsWith("Scraping")
            ? "text-yellow-400 bg-yellow-950/40 border-yellow-500/20"
            : "text-gray-400 bg-gray-900 border-gray-800";

        const statusText = scan.status === "in_progress"
          ? "Running"
          : scan.status === "queued" || scan.status.startsWith("Starting")
            ? "Queued"
            : scan.status.startsWith("Scraping")
              ? scan.status
              : scan.status.charAt(0).toUpperCase() + scan.status.slice(1);

        const remainingSecs = Math.max(0, (scan.timestamp + scan.estimated_duration) - currentTime);
        const elapsedSecs = Math.max(0, currentTime - scan.timestamp);
        const progressPct = scan.estimated_duration > 0
          ? Math.min(100, Math.round((elapsedSecs / scan.estimated_duration) * 100))
          : 0;
        const fmtTime = (secs: number) => {
          const h = Math.floor(secs / 3600);
          const m = Math.floor((secs % 3600) / 60);
          const s = secs % 60;
          return `${h > 0 ? `${h}h ` : ""}${m > 0 ? `${m}m ` : ""}${s}s`;
        };

        return (
          <div key={scan.scan_id} className="rounded-lg border border-indigo-500/20 bg-indigo-950/20 p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className={`shrink-0 ${scan.status === "in_progress" || scan.status.startsWith("Scraping") ? "animate-spin" : ""}`}>
                  {scan.status === "in_progress" || scan.status.startsWith("Scraping") ? "🌀" : "⏳"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-semibold text-xs text-indigo-300">{batchTitle}</span>
                    <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold border ${statusColor}`}>{statusText}</span>
                    <span className="text-[10px] text-gray-500">{formattedDate}</span>
                  </div>
                  {/* Progress bar */}
                  <div className="mt-1.5 w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-indigo-500 h-full rounded-full transition-all duration-1000"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    {progressPct}% &middot; {remainingSecs > 0 ? `~${fmtTime(remainingSecs)} remaining` : `Running for ${fmtTime(elapsedSecs)}`}
                  </p>
                </div>
              </div>
              <div className="flex gap-1.5 shrink-0">
                <button
                  onClick={async () => {
                    setRefreshingId(scan.scan_id);
                    await onRefresh(scan.scan_id);
                    setRefreshingId(null);
                  }}
                  disabled={refreshingId === scan.scan_id}
                  className="rounded border border-gray-700 px-2 py-1 text-[10px] text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-50"
                >
                  {refreshingId === scan.scan_id ? "..." : "Refresh"}
                </button>
                <button
                  onClick={() => onCancel(scan.scan_id)}
                  className="rounded border border-red-800 px-2 py-1 text-[10px] text-red-400 hover:text-red-200 hover:border-red-600"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
