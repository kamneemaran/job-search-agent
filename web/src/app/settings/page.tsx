"use client";

import { useState, useEffect, useRef } from "react";
import {
  getProfile,
  updateProfile,
  getDigestPreferences,
  updateDigestPreferences,
  sendDigestNow,
  type Profile,
  type DigestPreferences,
} from "@/lib/api";
import { getBrowserClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  // Profile state
  const [name, setName] = useState("");
  const [currentRole, setCurrentRole] = useState("");
  const [yearsExperience, setYearsExperience] = useState(0);
  const [skillsInput, setSkillsInput] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [profileUpdatedAt, setProfileUpdatedAt] = useState("");

  // Digest state
  const [digestFrequency, setDigestFrequency] = useState("weekly");
  const [digestDayOfWeek, setDigestDayOfWeek] = useState("monday");
  const [digestDayOfMonth, setDigestDayOfMonth] = useState(1);
  const [digestTimeOfDay, setDigestTimeOfDay] = useState("09:00");
  const [digestEmail, setDigestEmail] = useState("");
  const [digestBatches, setDigestBatches] = useState<string[]>(["all"]);
  const [postedDateFilter, setPostedDateFilter] = useState("any");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState("");
  const [sendError, setSendError] = useState(false);
  const [sentHistory, setSentHistory] = useState<string[]>([]);
  const [lastScanJobs, setLastScanJobs] = useState<number | null>(null);

  // Modal state
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showSendNowModal, setShowSendNowModal] = useState(false);
  const [sendNowBatches, setSendNowBatches] = useState<string[]>(["all"]);
  const [sendNowDateFilter, setSendNowDateFilter] = useState("any");

  // Resume state
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [activeResume, setActiveResume] = useState("");
  const [resumeSkillsCount, setResumeSkillsCount] = useState(0);
  const [resumeUploadDate, setResumeUploadDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Webhook state
  const [webhookUrl, setWebhookUrl] = useState("");

  interface ActiveScan {
    scan_id: string;
    run_id: string;
    batches: string[];
    status: string;
    timestamp: number;
    estimated_duration: number;
  }

  interface ScanSummary {
    instant_completed_today: number;
    instant_failed_today: number;
    daily_completed_today: number;
    daily_failed_today: number;
    last_daily_status: string;
    last_daily_time: number;
  }

  const [activeScans, setActiveScans] = useState<ActiveScan[]>([]);
  const [scanSummary, setScanSummary] = useState<ScanSummary | null>(null);
  const [currentTime, setCurrentTime] = useState(Math.floor(Date.now() / 1000));
  const [refreshingId, setRefreshingId] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    const t = setInterval(() => {
      setCurrentTime(Math.floor(Date.now() / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const fetchActiveScans = async (refreshId?: string) => {
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;

      const res = await fetch(`${API_BASE}/api/digest/scans${refreshId ? `?refresh_id=${refreshId}` : ""}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setActiveScans(data.active_scans || []);
        setScanSummary(data.summary || null);
      }
    } catch (err) {
      console.error("Failed to fetch active scans:", err);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (activeScans.length > 0) {
      interval = setInterval(() => {
        fetchActiveScans();
      }, 120000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeScans]);

  const handleCancelScan = async (scanId: string) => {
    try {
      const supabase = (await import("@/lib/supabase/client")).getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) return;

      const res = await fetch(`${API_BASE}/api/digest/reset?scan_id=${scanId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSendResult(data.message);
        setSendError(false);
        await fetchActiveScans();
      } else {
        setSendResult("Failed to cancel scan");
        setSendError(true);
      }
    } catch (err) {
      setSendResult("Error cancelling scan");
      setSendError(true);
    }
    setTimeout(() => setSendResult(""), 5000);
  };

  const loadSettings = async () => {
    setLoading(true);
    try {
      const [profile, digest] = await Promise.all([
        getProfile().catch(() => ({ name: "", current_role: "", core_skills: [], years_experience: 0, seniority_keywords: [] })),
        getDigestPreferences().catch(() => ({ enabled: false, frequency: "weekly", email: "", day_of_week: "monday", day_of_month: 1, time_of_day: "09:00", sent_history: [], batches: ["all"], posted_date_filter: "any" })),
      ]);

      setName(profile.name || "");
      setCurrentRole(profile.current_role || "");
      setYearsExperience(profile.years_experience || 0);
      setSkills(profile.core_skills || []);
      setSkillsInput((profile.core_skills || []).join(", "));

      setDigestFrequency(digest.frequency || "weekly");
      setDigestDayOfWeek(digest.day_of_week || "monday");
      setDigestDayOfMonth(digest.day_of_month || 1);
      setDigestTimeOfDay(digest.time_of_day || "09:00");
      setDigestEmail(digest.email || "");
      setDigestBatches(digest.batches || ["all"]);
      setPostedDateFilter(digest.posted_date_filter || "any");
      setSentHistory(digest.sent_history || []);

      // Extract last scan job count from sent_history
      const completedEntries = (digest.sent_history || []).filter(
        (x: string) => typeof x === "string" && x.startsWith("COMPLETED_INSTANT:")
      );
      if (completedEntries.length > 0) {
        const last = completedEntries[completedEntries.length - 1];
        const jobsMatch = last.match(/jobs:(\d+)/);
        if (jobsMatch) setLastScanJobs(parseInt(jobsMatch[1], 10));
      }

      const supabase = getBrowserClient();
      if (!digest.email) {
        const { data } = await supabase.auth.getSession();
        if (data.session?.user?.email) {
          setDigestEmail(data.session.user.email);
        }
      }

      // Fetch active resume
      try {
        const { data: resumes } = await supabase
          .from("resumes")
          .select("filename, parsed_skills, created_at")
          .eq("is_active", true)
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (resumes) {
          setActiveResume(resumes.filename);
          const parsedSkills = resumes.parsed_skills;
          if (typeof parsedSkills === "string") {
            try { setResumeSkillsCount(JSON.parse(parsedSkills).length); } catch { setResumeSkillsCount(0); }
          } else if (Array.isArray(parsedSkills)) {
            setResumeSkillsCount(parsedSkills.length);
          }
          if (resumes.created_at) {
            setResumeUploadDate(new Date(resumes.created_at).toLocaleDateString());
          }
        }
      } catch (err) {
        console.error("Failed to fetch active resume:", err);
      }

      // Fetch profile updated_at
      try {
        const { data: profileRow } = await supabase
          .from("profiles")
          .select("updated_at")
          .maybeSingle();
        if (profileRow?.updated_at) {
          setProfileUpdatedAt(new Date(profileRow.updated_at).toLocaleDateString());
        }
      } catch {}

      // Fetch webhook URL
      try {
        const { data: prefRow } = await supabase
          .from("email_preferences")
          .select("webhook_url")
          .maybeSingle();
        if (prefRow?.webhook_url) {
          setWebhookUrl(prefRow.webhook_url);
        }
      } catch {}

      await fetchActiveScans();
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSkillsChange = (value: string) => {
    setSkillsInput(value);
    setSkills(
      value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    );
  };

  const removeSkill = (index: number) => {
    const updated = skills.filter((_, i) => i !== index);
    setSkills(updated);
    setSkillsInput(updated.join(", "));
  };

  const handleUpdateProfile = async () => {
    setSaving(true);
    setMessage("");
    try {
      await updateProfile({
        name,
        current_role: currentRole,
        core_skills: skills,
        years_experience: yearsExperience,
      });
      setMessage("Profile updated successfully.");
      setProfileUpdatedAt(new Date().toLocaleDateString());
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : "Update failed"}`);
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(""), 3000);
    }
  };

  const handleResumeUpload = async () => {
    if (!resumeFile) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const supabase = getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) throw new Error("Not authenticated");

      const formData = new FormData();
      formData.append("file", resumeFile);

      const res = await fetch(`${API_BASE}/api/resume/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setUploadMsg(`Uploaded! ${data.core_skills?.length || 0} skills extracted.`);
        setActiveResume(resumeFile.name);
        setResumeSkillsCount(data.core_skills?.length || 0);
        setResumeUploadDate(new Date().toLocaleDateString());
        setResumeFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      } else {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        setUploadMsg(`Error: ${err.detail || "Upload failed"}`);
      }
    } catch (err) {
      setUploadMsg(`Error: ${err instanceof Error ? err.message : "Upload failed"}`);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadMsg(""), 5000);
    }
  };

  const handleSaveSchedule = async () => {
    setSaving(true);
    try {
      await updateDigestPreferences({
        enabled: digestFrequency !== "never",
        frequency: digestFrequency,
        email: digestEmail,
        day_of_week: digestDayOfWeek,
        day_of_month: digestDayOfMonth,
        time_of_day: digestTimeOfDay,
        batches: digestBatches,
        posted_date_filter: postedDateFilter,
      });
      setShowScheduleModal(false);
      setSendResult("Schedule saved successfully.");
      setSendError(false);
    } catch (err) {
      setSendResult(`Error: ${err instanceof Error ? err.message : "Save failed"}`);
      setSendError(true);
    } finally {
      setSaving(false);
      setTimeout(() => setSendResult(""), 4000);
    }
  };

  const handleSendNow = async () => {
    setSending(true);
    setSendResult("");
    setSendError(false);
    try {
      const res = await sendDigestNow(digestEmail, "now", sendNowBatches, sendNowDateFilter);
      setSendResult(res.message);
      const isMsgError = res.message.toLowerCase().includes("fail") ||
        res.message.toLowerCase().includes("error") ||
        res.message.toLowerCase().includes("limit") ||
        res.message.toLowerCase().includes("unauthorized") ||
        !res.sent;
      if (isMsgError) {
        setSendError(true);
      }
      setShowSendNowModal(false);
      await fetchActiveScans();
    } catch (err) {
      setSendResult(err instanceof Error ? err.message : "Failed to send digest");
      setSendError(true);
    } finally {
      setSending(false);
      setTimeout(() => setSendResult(""), 5000);
    }
  };

  const BATCH_OPTIONS = [
    { id: "all", label: "All Regions (Master Scan)", est: "~3h" },
    { id: "india", label: "India", est: "~20 min" },
    { id: "europe_companies", label: "Europe Companies", est: "~45 min" },
    { id: "europe_boards", label: "Europe Job Boards", est: "~20 min" },
    { id: "middle_east", label: "Middle East", est: "~15 min" },
    { id: "apac", label: "APAC", est: "~15 min" },
    { id: "us_canada", label: "US & Canada", est: "~15 min" },
    { id: "remote", label: "Remote (Global)", est: "~30 min" },
  ];

  const DATE_FILTER_OPTIONS = [
    { value: "any", label: "Any Time" },
    { value: "1d", label: "Last 24 Hours" },
    { value: "1w", label: "Last 1 Week" },
    { value: "1m", label: "Last 1 Month" },
    { value: "3m", label: "Last 3 Months" },
  ];

  const BatchSelector = ({ batches, setBatches, showEst }: { batches: string[]; setBatches: (b: string[]) => void; showEst?: boolean }) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {BATCH_OPTIONS.map((batch) => (
        <label key={batch.id} className="inline-flex items-center gap-2 text-sm cursor-pointer text-gray-300 hover:text-white">
          <input
            type="checkbox"
            checked={batches.includes(batch.id)}
            onChange={(e) => {
              if (batch.id === "all") {
                setBatches(e.target.checked ? ["all"] : []);
              } else {
                let updated = [...batches].filter((x) => x !== "all");
                if (e.target.checked) {
                  updated.push(batch.id);
                } else {
                  updated = updated.filter((x) => x !== batch.id);
                }
                setBatches(updated.length === 0 ? ["all"] : updated);
              }
            }}
            className="rounded border-gray-700 bg-gray-800 text-indigo-600 focus:ring-indigo-500"
          />
          <span>{batch.label}</span>
          {showEst && <span className="text-[10px] text-gray-600">{batch.est}</span>}
        </label>
      ))}
    </div>
  );

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="text-center py-16 text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-3xl font-bold mb-2">Settings</h1>
      <p className="text-gray-400 text-sm mb-8">
        Manage your profile, resume, and email digest.
      </p>

      <div className="space-y-6">
        {/* Profile Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Profile</h2>
            {profileUpdatedAt && (
              <span className="text-[10px] text-gray-600">Last updated: {profileUpdatedAt}</span>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                placeholder="John Doe"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Current Role</label>
              <input
                type="text"
                value={currentRole}
                onChange={(e) => setCurrentRole(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                placeholder="Senior Software Engineer"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Years of Experience</label>
              <input
                type="number"
                value={yearsExperience}
                onChange={(e) => setYearsExperience(Number(e.target.value))}
                min={0}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Core Skills (comma-separated)</label>
              <input
                type="text"
                value={skillsInput}
                onChange={(e) => handleSkillsChange(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                placeholder="Python, TypeScript, AWS"
              />
            </div>
          </div>
          {skills.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {skills.map((skill, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400"
                >
                  {skill}
                  <button onClick={() => removeSkill(i)} className="ml-0.5 text-indigo-400 hover:text-white">&times;</button>
                </span>
              ))}
            </div>
          )}
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleUpdateProfile}
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Updating..." : "Update Profile"}
            </button>
            {message && (
              <p className={`text-sm ${message.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>
                {message}
              </p>
            )}
          </div>
        </div>

        {/* Resume Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Resume</h2>
          {activeResume ? (
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm text-gray-300">{activeResume}</p>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  {resumeSkillsCount > 0 && <span className="text-indigo-400">{resumeSkillsCount} skills extracted</span>}
                  {resumeUploadDate && <span className="ml-2">Uploaded: {resumeUploadDate}</span>}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 mb-3">No resume uploaded. Upload one to improve job matching.</p>
          )}
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              className="text-sm text-gray-400 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-800 file:px-3 file:py-1.5 file:text-sm file:text-gray-300 file:cursor-pointer hover:file:bg-gray-700"
            />
            {resumeFile && (
              <button
                onClick={handleResumeUpload}
                disabled={uploading}
                className="rounded-lg bg-emerald-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            )}
          </div>
          {uploadMsg && (
            <p className={`mt-2 text-xs ${uploadMsg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{uploadMsg}</p>
          )}
        </div>

        {/* Email Digest Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Email Digest</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Email: <span className="text-gray-300">{digestEmail || "not set"}</span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowScheduleModal(true)}
                className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-xs sm:text-sm font-semibold text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
              >
                Schedule
              </button>
              <button
                onClick={() => {
                  setSendNowBatches([...digestBatches]);
                  setSendNowDateFilter(postedDateFilter);
                  setShowSendNowModal(true);
                }}
                disabled={sending || activeScans.length >= 5}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {activeScans.length >= 5 ? "Limit Reached" : "Send Now"}
              </button>
            </div>
          </div>

          {/* Scan Summary */}
          {scanSummary && (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-4">
              <div className="rounded-lg border border-gray-800/40 bg-gray-900/30 p-3">
                <span className="text-[10px] text-gray-500 font-medium">On-Demand (Today)</span>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-emerald-400 font-bold text-lg">{scanSummary.instant_completed_today}</span>
                  <span className="text-emerald-500 text-[10px]">done</span>
                  {scanSummary.instant_failed_today > 0 && (
                    <>
                      <span className="ml-1 text-red-400 font-bold">{scanSummary.instant_failed_today}</span>
                      <span className="text-red-500 text-[10px]">failed</span>
                    </>
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800/40 bg-gray-900/30 p-3">
                <span className="text-[10px] text-gray-500 font-medium">Last Scan Result</span>
                <div className="mt-1">
                  {lastScanJobs !== null ? (
                    <span className="text-indigo-400 font-bold text-lg">{lastScanJobs} <span className="text-[10px] font-normal">matches</span></span>
                  ) : (
                    <span className="text-gray-500 text-xs">No data</span>
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800/40 bg-gray-900/30 p-3">
                <span className="text-[10px] text-gray-500 font-medium">Scheduled Digest</span>
                <div className="mt-1">
                  <span className={`font-semibold text-xs ${
                    scanSummary.last_daily_status === "Completed" ? "text-emerald-400"
                      : scanSummary.last_daily_status === "Failed" ? "text-red-400"
                      : "text-gray-400"
                  }`}>{scanSummary.last_daily_status}</span>
                  {scanSummary.last_daily_time > 0 && (
                    <span className="text-[9px] text-gray-500 ml-1">
                      {new Date(scanSummary.last_daily_time * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800/40 bg-gray-900/30 p-3">
                <span className="text-[10px] text-gray-500 font-medium">Schedule</span>
                <div className="mt-1">
                  <span className={`font-semibold text-xs ${digestFrequency === "never" ? "text-gray-500" : "text-indigo-400"}`}>
                    {digestFrequency === "never" ? "Disabled" : digestFrequency.charAt(0).toUpperCase() + digestFrequency.slice(1)}
                  </span>
                  {digestFrequency === "weekly" && <span className="text-[9px] text-gray-500 ml-1">{digestDayOfWeek.charAt(0).toUpperCase() + digestDayOfWeek.slice(1)}</span>}
                  {digestFrequency === "daily" && <span className="text-[9px] text-gray-500 ml-1">at {digestTimeOfDay}</span>}
                  {digestFrequency === "monthly" && <span className="text-[9px] text-gray-500 ml-1">Day {digestDayOfMonth}</span>}
                </div>
              </div>
            </div>
          )}

          {sendResult && (
            <p className={`mb-4 text-xs font-semibold ${sendError ? "text-red-400" : "text-emerald-400"}`}>
              {sendResult}
            </p>
          )}

          {/* Active Scans */}
          {activeScans.length > 0 && (
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
                            await fetchActiveScans(scan.scan_id);
                            setRefreshingId(null);
                          }}
                          disabled={refreshingId === scan.scan_id}
                          className="rounded border border-gray-700 px-2 py-1 text-[10px] text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-50"
                        >
                          {refreshingId === scan.scan_id ? "..." : "Refresh"}
                        </button>
                        <button
                          onClick={() => handleCancelScan(scan.scan_id)}
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
          )}

        </div>

        {/* Webhook / Notifications Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-1">Notifications</h2>
          <p className="text-xs text-gray-500 mb-3">Get notified on Slack, Discord, or any webhook when scans complete.</p>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Webhook URL (optional)</label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              placeholder="https://hooks.slack.com/services/... or Discord webhook URL"
            />
            <p className="text-[10px] text-gray-600 mt-1">
              We'll POST a JSON summary when each scan completes. Works with Slack, Discord, Zapier, n8n, etc.
            </p>
          </div>
          <button
            onClick={async () => {
              try {
                const supabase = getBrowserClient();
                const { data: session } = await supabase.auth.getSession();
                const token = session?.session?.access_token;
                if (!token) return;
                const res = await fetch(`${API_BASE}/api/digest/preferences`, {
                  method: "PUT",
                  headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                  body: JSON.stringify({ webhook_url: webhookUrl, enabled: digestFrequency !== "never", frequency: digestFrequency, email: digestEmail, day_of_week: digestDayOfWeek, day_of_month: digestDayOfMonth, time_of_day: digestTimeOfDay, batches: digestBatches, posted_date_filter: postedDateFilter }),
                });
                if (res.ok) setSendResult("Webhook saved.");
                else setSendResult("Failed to save webhook.");
              } catch { setSendResult("Error saving webhook."); }
              setSendError(false);
              setTimeout(() => setSendResult(""), 3000);
            }}
            className="mt-3 rounded-lg bg-gray-800 border border-gray-700 px-4 py-1.5 text-xs text-gray-300 hover:bg-gray-700 hover:text-white"
          >
            Save Webhook
          </button>
        </div>
      </div>

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowScheduleModal(false)}>
          <div className="w-full max-w-lg mx-4 rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-white mb-4">Schedule Email Digest</h3>

            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Email Address</label>
                <input
                  type="email"
                  value={digestEmail}
                  onChange={(e) => setDigestEmail(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Frequency</label>
                <select
                  value={digestFrequency}
                  onChange={(e) => setDigestFrequency(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="never">Never (Disabled)</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              {digestFrequency === "weekly" && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Day of Week</label>
                  <select
                    value={digestDayOfWeek}
                    onChange={(e) => setDigestDayOfWeek(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none capitalize"
                  >
                    {["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].map(d => (
                      <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                    ))}
                  </select>
                </div>
              )}

              {digestFrequency === "monthly" && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Day of Month</label>
                  <select
                    value={digestDayOfMonth}
                    onChange={(e) => setDigestDayOfMonth(Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                  >
                    {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                      <option key={day} value={day}>Day {day}</option>
                    ))}
                  </select>
                </div>
              )}

              {digestFrequency === "daily" && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Time of Day</label>
                  <select
                    value={digestTimeOfDay}
                    onChange={(e) => setDigestTimeOfDay(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                  >
                    {Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}:00`).map((time) => (
                      <option key={time} value={time}>{time}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-sm text-gray-400 mb-1">Job Age Filter</label>
                <select
                  value={postedDateFilter}
                  onChange={(e) => setPostedDateFilter(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  {DATE_FILTER_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Job Boards / Regions</label>
                <BatchSelector batches={digestBatches} setBatches={setDigestBatches} />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-800">
              <button
                onClick={() => setShowScheduleModal(false)}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:text-white hover:border-gray-500"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveSchedule}
                disabled={saving}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Schedule"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Send Now Modal */}
      {showSendNowModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowSendNowModal(false)}>
          <div className="w-full max-w-lg mx-4 rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-white mb-4">Run Scan Now</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Job Age Filter</label>
                <select
                  value={sendNowDateFilter}
                  onChange={(e) => setSendNowDateFilter(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  {DATE_FILTER_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-2">Job Boards / Regions</label>
                <BatchSelector batches={sendNowBatches} setBatches={setSendNowBatches} showEst />
              </div>

              <p className="text-xs text-gray-500">
                Results will be sent to <span className="text-gray-300 font-medium">{digestEmail || "your email"}</span>
              </p>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-800">
              <button
                onClick={() => setShowSendNowModal(false)}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 hover:text-white hover:border-gray-500"
              >
                Cancel
              </button>
              <button
                onClick={handleSendNow}
                disabled={sending}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {sending ? "Starting..." : "Start Scan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
