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

const STATUS_OPTIONS = ["new", "applied", "rejected", "offer"];

export default function DashboardPage() {
  const [jobs, setJobs] = useState<TrackerJob[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState("");

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

  const handleSaveNotes = async (title: string, company: string) => {
    try {
      const job = jobs.find((j) => j.title === title && j.company === company);
      await updateTracker({ title, company, status: job?.status || "new", notes: editNotes });
      setJobs((prev) =>
        prev.map((j) =>
          j.title === title && j.company === company
            ? { ...j, notes: editNotes, date_updated: new Date().toISOString() }
            : j
        )
      );
      setEditing(null);
    } catch (err) {
      console.error("Update notes failed:", err);
    }
  };

  const counts = {
    all: jobs.length,
    new: jobs.filter((j) => j.status === "new").length,
    applied: jobs.filter((j) => j.status === "applied").length,
    rejected: jobs.filter((j) => j.status === "rejected").length,
    offer: jobs.filter((j) => j.status === "offer").length,
  };

  const formatDate = (d: string) => {
    if (!d) return "";
    try {
      return new Date(d).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return d;
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
      <p className="text-gray-400 text-sm mb-8">
        Track your job applications. Update status and add notes as you progress.
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
          {jobs.map((job, i) => {
            const editKey = `${job.company}|${job.title}`;
            const isEditing = editing === editKey;
            return (
              <div
                key={editKey + i}
                className="rounded-xl border border-gray-800 bg-gray-900/50 p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Title + Status */}
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-semibold text-white truncate">
                        {job.title}
                      </h3>
                      <select
                        value={job.status}
                        onChange={(e) =>
                          handleStatus(job.title, job.company, e.target.value)
                        }
                        className={`rounded-md border px-2 py-0.5 text-xs font-bold bg-transparent cursor-pointer ${
                          STATUS_COLORS[job.status] || STATUS_COLORS.new
                        }`}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s} className="bg-gray-800 text-white">
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                          </option>
                        ))}
                      </select>
                      {job.score > 0 && (
                        <span className="text-xs text-gray-500">
                          Score: {job.score}
                        </span>
                      )}
                    </div>

                    {/* Company + Dates */}
                    <div className="text-sm text-gray-400 mb-1">
                      {job.company}
                      {job.url && (
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-2 text-indigo-400 hover:text-indigo-300 text-xs"
                        >
                          View posting
                        </a>
                      )}
                    </div>
                    <div className="text-xs text-gray-600 mb-2">
                      Added: {formatDate(job.date_found)}
                      {job.date_updated && job.date_updated !== job.date_found && (
                        <> · Updated: {formatDate(job.date_updated)}</>
                      )}
                    </div>

                    {/* Notes */}
                    {isEditing ? (
                      <div className="flex items-center gap-2 mt-2">
                        <input
                          type="text"
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="Add notes..."
                          className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveNotes(job.title, job.company)}
                          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditing(null)}
                          className="rounded-lg bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-gray-700"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : job.notes ? (
                      <p
                        className="text-xs text-gray-500 cursor-pointer hover:text-gray-400 mt-1"
                        onClick={() => {
                          setEditing(editKey);
                          setEditNotes(job.notes);
                        }}
                      >
                        📝 {job.notes}
                      </p>
                    ) : (
                      <button
                        onClick={() => {
                          setEditing(editKey);
                          setEditNotes("");
                        }}
                        className="text-xs text-gray-600 hover:text-gray-400 mt-1"
                      >
                        + Add notes
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
