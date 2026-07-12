"use client";

import { useState, useEffect } from "react";
import {
  getTracker,
  updateTracker,
  type TrackerJob,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  applied: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  rejected: "bg-red-500/10 text-red-400 border-red-500/30",
  offer: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
};

export default function DashboardPage() {
  const [jobs, setJobs] = useState<TrackerJob[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const loadJobs = async (status?: string) => {
    setLoading(true);
    try {
      const res = await getTracker(status);
      setJobs(res.jobs);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs(filter || undefined);
  }, [filter]);

  const handleStatus = async (
    title: string,
    company: string,
    status: string
  ) => {
    try {
      await updateTracker({ title, company, status });
      setJobs((prev) =>
        prev.map((j) =>
          j.title === title && j.company === company
            ? { ...j, status, date_updated: new Date().toISOString() }
            : j
        )
      );
    } catch (err) {
      console.error("Update failed:", err);
    }
  };

  const counts = {
    all: jobs.length,
    new: jobs.filter((j) => j.status === "new").length,
    applied: jobs.filter((j) => j.status === "applied").length,
    rejected: jobs.filter((j) => j.status === "rejected").length,
    offer: jobs.filter((j) => j.status === "offer").length,
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
      <p className="text-gray-400 text-sm mb-8">
        Track your job applications. Update status as you progress.
      </p>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto">
        {(["", "new", "applied", "rejected", "offer"] as const).map((s) => (
          <button
            key={s || "all"}
            onClick={() => setFilter(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === s
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {s === "" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="ml-1.5 text-xs opacity-60">
              {s === "" ? counts.all : counts[s as keyof typeof counts]}
            </span>
          </button>
        ))}
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          No tracked jobs yet. Search and add jobs to start tracking.
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job, i) => (
            <div
              key={`${job.company}-${job.title}-${i}`}
              className="rounded-xl border border-gray-800 bg-gray-900/50 p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="font-semibold text-white truncate">
                      {job.title}
                    </h3>
                    <span
                      className={`flex-shrink-0 rounded-md border px-2.5 py-0.5 text-xs font-bold ${
                        STATUS_COLORS[job.status] || STATUS_COLORS.new
                      }`}
                    >
                      {job.status}
                    </span>
                    {job.score > 0 && (
                      <span className="text-xs text-gray-500">
                        Score: {job.score}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-400 mb-1">
                    {job.company}
                  </div>
                  {job.notes && (
                    <p className="text-xs text-gray-500">{job.notes}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
                    >
                      View
                    </a>
                  )}
                  {job.status !== "applied" && (
                    <button
                      onClick={() =>
                        handleStatus(job.title, job.company, "applied")
                      }
                      className="rounded-lg bg-yellow-600/20 border border-yellow-600/30 px-3 py-1.5 text-xs text-yellow-400 hover:bg-yellow-600/30 transition-colors"
                    >
                      Applied
                    </button>
                  )}
                  {job.status !== "rejected" && (
                    <button
                      onClick={() =>
                        handleStatus(job.title, job.company, "rejected")
                      }
                      className="rounded-lg bg-red-600/20 border border-red-600/30 px-3 py-1.5 text-xs text-red-400 hover:bg-red-600/30 transition-colors"
                    >
                      Reject
                    </button>
                  )}
                  {job.status !== "offer" && (
                    <button
                      onClick={() =>
                        handleStatus(job.title, job.company, "offer")
                      }
                      className="rounded-lg bg-emerald-600/20 border border-emerald-600/30 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-600/30 transition-colors"
                    >
                      Offer
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
