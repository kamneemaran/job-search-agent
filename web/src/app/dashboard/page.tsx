"use client";

import { useState, useEffect, useRef } from "react";
import {
  getTracker,
  updateTracker,
  type TrackerJob,
} from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
  const [sortBy, setSortBy] = useState("newest");
  const [currentPage, setCurrentPage] = useState(1);
  const jobsPerPage = 5;
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setCurrentPage(1);
  }, [filter, sortBy]);

  // Advanced Editing State
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editSalary, setEditSalary] = useState("");
  const [editStatus, setEditStatus] = useState("new");

  // Sheet state
  const [sheetUrl, setSheetUrl] = useState("");
  const [sheetInput, setSheetInput] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [sheetMsg, setSheetMsg] = useState("");

  // Import/export state
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load all jobs on mount to allow instant client-side switching and correct counters
  const loadJobs = async () => {
    setLoading(true);
    try {
      const res = await getTracker();
      setJobs(res.jobs);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  const loadSheet = async () => {
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/tracker/sheet`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSheetUrl(data.url || "");
        setSheetInput(data.url || "");
      }
    } catch {}
  };

  useEffect(() => {
    loadJobs();
    loadSheet();
  }, []);

  const handleStatusChange = async (title: string, company: string, status: string) => {
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
      console.error("Update status failed:", err);
    }
  };

  const startEditing = (job: TrackerJob) => {
    setEditingKey(`${job.company}|${job.title}`);
    setEditTitle(job.title);
    setEditCompany(job.company);
    setEditUrl(job.url || "");
    setEditNotes(job.notes || "");
    setEditLocation(job.location || "");
    setEditSalary(job.salary || "");
    setEditStatus(job.status);
  };

  const handleSaveEdit = async (originalTitle: string, originalCompany: string) => {
    try {
      await updateTracker({
        title: originalTitle,
        company: originalCompany,
        status: editStatus,
        notes: editNotes,
        new_title: editTitle !== originalTitle ? editTitle : undefined,
        new_company: editCompany !== originalCompany ? editCompany : undefined,
        url: editUrl,
        location: editLocation,
        salary: editSalary,
      });

      setJobs((prev) =>
        prev.map((j) =>
          j.title === originalTitle && j.company === originalCompany
            ? {
                ...j,
                title: editTitle,
                company: editCompany,
                url: editUrl,
                notes: editNotes,
                location: editLocation,
                salary: editSalary,
                status: editStatus,
                date_updated: new Date().toISOString(),
              }
            : j
        )
      );
      setEditingKey(null);
    } catch (err) {
      console.error("Save edit failed:", err);
      alert("Failed to save changes. Make sure Title and Company do not duplicate an existing job.");
    }
  };

  const handleSaveSheet = async () => {
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/tracker/sheet`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ url: sheetInput }),
      });
      if (res.ok) {
        setSheetUrl(sheetInput);
        setSheetMsg("Sheet link saved!");
      } else {
        setSheetMsg("Failed to save sheet link");
      }
    } catch {
      setSheetMsg("Failed to save");
    }
    setTimeout(() => setSheetMsg(""), 3000);
  };

  const handleSync = async () => {
    setSyncing(true);
    setSheetMsg("");
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/tracker/sheet/sync`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSheetMsg(`Synced ${data.count} jobs to sheet!`);
      } else {
        const err = await res.json();
        setSheetMsg(err.detail || "Sync failed");
      }
    } catch {
      setSheetMsg("Sync failed");
    }
    setSyncing(false);
    setTimeout(() => setSheetMsg(""), 5000);
  };

  const handlePull = async () => {
    setPulling(true);
    setSheetMsg("");
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/tracker/sheet/pull`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSheetMsg(`Imported ${data.inserted} new jobs, updated ${data.updated} jobs from sheet!`);
        await loadJobs(); // Reload dashboard jobs
      } else {
        const err = await res.json();
        setSheetMsg(err.detail || "Import from sheet failed");
      }
    } catch {
      setSheetMsg("Import from sheet failed");
    }
    setPulling(false);
    setTimeout(() => setSheetMsg(""), 5000);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportMsg("");
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/tracker/import`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setImportMsg(`Imported ${data.added} jobs${data.skipped_duplicates > 0 ? ` (${data.skipped_duplicates} duplicates skipped)` : ""}!`);
        loadJobs();
      } else {
        const err = await res.json();
        setImportMsg(err.detail || "Import failed");
      }
    } catch {
      setImportMsg("Import failed");
    }
    setImporting(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setTimeout(() => setImportMsg(""), 5000);
  };

  const handleExport = async () => {
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/tracker/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "job_tracker_export.csv";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {}
  };

  // Client-side statistics & filters (fixed "counters resetting to 0" issue)
  const counts = {
    all: jobs.length,
    new: jobs.filter((j) => j.status === "new").length,
    applied: jobs.filter((j) => j.status === "applied").length,
    rejected: jobs.filter((j) => j.status === "rejected").length,
    offer: jobs.filter((j) => j.status === "offer").length,
  };

  const filteredJobs = filter ? jobs.filter((j) => j.status === filter) : jobs;

  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (sortBy === "newest") {
      const dA = a.date_found ? new Date(a.date_found).getTime() : 0;
      const dB = b.date_found ? new Date(b.date_found).getTime() : 0;
      return dB - dA;
    } else if (sortBy === "oldest") {
      const dA = a.date_found ? new Date(a.date_found).getTime() : 0;
      const dB = b.date_found ? new Date(b.date_found).getTime() : 0;
      return dA - dB;
    } else if (sortBy === "score_desc") {
      return (b.score || 0) - (a.score || 0);
    } else if (sortBy === "score_asc") {
      return (a.score || 0) - (b.score || 0);
    } else if (sortBy === "title_az") {
      return a.title.localeCompare(b.title);
    } else if (sortBy === "company_az") {
      return a.company.localeCompare(b.company);
    }
    return 0;
  });

  const totalPages = Math.ceil(sortedJobs.length / jobsPerPage);
  const paginatedJobs = sortedJobs.slice((currentPage - 1) * jobsPerPage, currentPage * jobsPerPage);

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
        Track your job applications. Connect a Google Sheet to sync your data.
      </p>

      {/* Google Sheet Integration */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 mb-8">
        <h2 className="text-lg font-semibold text-white mb-2">📊 Google Sheet Sync</h2>
        <p className="text-xs text-gray-500 mb-4">
          Connect your own Google Sheet to export your tracked jobs. 
          Create a sheet, share it with <code className="text-indigo-400">kminterviewer@jobpilot-449312.iam.gserviceaccount.com</code> as Editor, then paste the URL below.
        </p>
        <div className="flex items-center gap-3">
          <input
            type="url"
            value={sheetInput}
            onChange={(e) => setSheetInput(e.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/..."
            className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
          />
          <button
            onClick={handleSaveSheet}
            className="rounded-lg bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600 transition-colors"
          >
            Save URL
          </button>
          <button
            onClick={handleSync}
            disabled={syncing || pulling || !sheetUrl}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {syncing ? "Exporting..." : "Export to Sheet"}
          </button>
          <button
            onClick={handlePull}
            disabled={syncing || pulling || !sheetUrl}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {pulling ? "Importing..." : "Import from Sheet"}
          </button>
        </div>
        {sheetMsg && (
          <p className={`text-xs mt-2 ${sheetMsg.includes("Failed") ? "text-red-400" : "text-emerald-400"}`}>
            {sheetMsg}
          </p>
        )}
        {sheetUrl && (
          <a
            href={sheetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-2 text-xs text-indigo-400 hover:text-indigo-300"
          >
            Open your tracker sheet &rarr;
          </a>
        )}
      </div>

      {/* Import / Export */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 mb-8">
        <h2 className="text-lg font-semibold text-white mb-2">📁 Import / Export</h2>
        <p className="text-xs text-gray-500 mb-4">
          Upload a CSV of jobs to bulk-add to your tracker, or export your tracker as CSV.
          The CSV should have columns like <code className="text-indigo-400">Title</code>, <code className="text-indigo-400">Company</code>, <code className="text-indigo-400">Location</code>, <code className="text-indigo-400">URL</code>, <code className="text-indigo-400">Status</code>.
        </p>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleImport}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="rounded-lg bg-gray-700 px-4 py-2 text-sm text-white hover:bg-gray-600 disabled:opacity-50 transition-colors"
          >
            {importing ? "Importing..." : "Import CSV"}
          </button>
          <button
            onClick={handleExport}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 transition-colors"
          >
            Export CSV
          </button>
        </div>
        {importMsg && (
          <p className={`text-xs mt-2 ${importMsg.includes("Failed") ? "text-red-400" : "text-emerald-400"}`}>
            {importMsg}
          </p>
        )}
      </div>

      {/* Filter and Sort Row */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6 border-b border-gray-800 pb-4">
        {/* Filter Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto">
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

        {/* Sort By Dropdown */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 whitespace-nowrap">Sort by</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs sm:text-sm text-white focus:border-indigo-500 focus:outline-none"
          >
            <option value="newest">Newest (Updated)</option>
            <option value="oldest">Oldest (Updated)</option>
            <option value="score_desc">Score: Highest First</option>
            <option value="score_asc">Score: Lowest First</option>
            <option value="title_az">Title: A-Z</option>
            <option value="company_az">Company: A-Z</option>
          </select>
        </div>
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading...</div>
      ) : sortedJobs.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          No jobs found in this section. Add or import jobs to track.
        </div>
      ) : (
        <div className="space-y-3">
          {paginatedJobs.map((job, i) => {
            const editKey = `${job.company}|${job.title}`;
            const isEditing = editingKey === editKey;
            return (
              <div key={editKey + i} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {isEditing ? (
                      /* Expanded Complete Editing Form */
                      <div className="space-y-3 mt-2 border-l-2 border-indigo-500 pl-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">Job Title</label>
                            <input
                              type="text"
                              value={editTitle}
                              onChange={(e) => setEditTitle(e.target.value)}
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">Company</label>
                            <input
                              type="text"
                              value={editCompany}
                              onChange={(e) => setEditCompany(e.target.value)}
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">Location</label>
                            <input
                              type="text"
                              value={editLocation}
                              onChange={(e) => setEditLocation(e.target.value)}
                              placeholder="e.g. Remote, Berlin"
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">Salary</label>
                            <input
                              type="text"
                              value={editSalary}
                              onChange={(e) => setEditSalary(e.target.value)}
                              placeholder="e.g. $120,000"
                              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">URL</label>
                          <input
                            type="text"
                            value={editUrl}
                            onChange={(e) => setEditUrl(e.target.value)}
                            placeholder="e.g. https://company.com/job"
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Notes</label>
                          <input
                            type="text"
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            placeholder="Add application notes..."
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Status</label>
                          <select
                            value={editStatus}
                            onChange={(e) => setEditStatus(e.target.value)}
                            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                          >
                            {STATUS_OPTIONS.map((s) => (
                              <option key={s} value={s}>
                                {s.charAt(0).toUpperCase() + s.slice(1)}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="flex items-center gap-2 pt-2">
                          <button
                            onClick={() => handleSaveEdit(job.title, job.company)}
                            className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                          >
                            Save Changes
                          </button>
                          <button
                            onClick={() => setEditingKey(null)}
                            className="rounded-lg bg-gray-800 border border-gray-700 px-4 py-2 text-xs font-semibold text-gray-400 hover:bg-gray-700"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Standard Job View Mode */
                      <>
                        <div className="flex items-center gap-3 mb-1">
                          <h3 className="font-semibold text-white truncate">{job.title}</h3>
                          <select
                            value={job.status}
                            onChange={(e) => handleStatusChange(job.title, job.company, e.target.value)}
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
                          {job.score > 0 && <span className="text-xs text-gray-500">Score: {job.score}</span>}
                          <button
                            onClick={() => startEditing(job)}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium ml-2"
                          >
                            ✏️ Edit Details
                          </button>
                        </div>
                        <div className="text-sm text-gray-400 mb-1">
                          {job.company}
                          {job.location && <span className="text-gray-500"> · {job.location}</span>}
                          {job.salary && <span className="ml-2 text-emerald-400">{job.salary}</span>}
                          {job.url && (
                            <a href={job.url} target="_blank" rel="noopener noreferrer" className="ml-2 text-indigo-400 hover:text-indigo-300 text-xs">
                              View posting &rarr;
                            </a>
                          )}
                        </div>
                        <div className="text-xs text-gray-600 mb-2">
                          Added: {formatDate(job.date_found)}
                          {job.date_updated && job.date_updated !== job.date_found && (
                            <> · Updated: {formatDate(job.date_updated)}</>
                          )}
                        </div>
                        {job.notes ? (
                          <p className="text-xs text-gray-500 cursor-pointer hover:text-gray-400 mt-1" onClick={() => startEditing(job)}>
                            📝 {job.notes}
                          </p>
                        ) : (
                          <button onClick={() => startEditing(job)} className="text-xs text-gray-600 hover:text-gray-400 mt-1">
                            + Add notes/details
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8 pt-4 border-t border-gray-800">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="rounded-lg bg-gray-800 border border-gray-700 px-3 py-1.5 text-xs font-semibold text-gray-400 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                Previous
              </button>
              
              <div className="flex items-center gap-1">
                {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                      currentPage === page
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700"
                    }`}
                  >
                    {page}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="rounded-lg bg-gray-800 border border-gray-700 px-3 py-1.5 text-xs font-semibold text-gray-400 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
