"use client";

import { useState, useEffect } from "react";
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

  // Digest state
  const [digestFrequency, setDigestFrequency] = useState("weekly");
  const [digestDayOfWeek, setDigestDayOfWeek] = useState("monday");
  const [digestDayOfMonth, setDigestDayOfMonth] = useState(1);
  const [digestTimeOfDay, setDigestTimeOfDay] = useState("09:00");
  const [digestEmail, setDigestEmail] = useState("");
  const [digestBatches, setDigestBatches] = useState<string[]>(["all"]);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState("");
  const [sendError, setSendError] = useState(false);
  const [sentHistory, setSentHistory] = useState<string[]>([]);

  // Resume state
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [activeResume, setActiveResume] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    const isScanning = sentHistory.some((x) => x.startsWith("RUNNING:"));

    if (isScanning) {
      interval = setInterval(async () => {
        try {
          const digest = await getDigestPreferences();
          const newHistory = digest.sent_history || [];
          setSentHistory(newHistory);
          
          const stillScanning = newHistory.some((x) => x.startsWith("RUNNING:"));
          if (!stillScanning) {
            setSendResult("Digest was completed, check your email!");
            setSendError(false);
          }
        } catch (err) {
          console.error("Polling status failed:", err);
        }
      }, 10000); // Poll every 10s
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [sentHistory]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const [profile, digest] = await Promise.all([
        getProfile().catch(() => ({ name: "", current_role: "", core_skills: [], years_experience: 0, seniority_keywords: [] })),
        getDigestPreferences().catch(() => ({ enabled: false, frequency: "weekly", email: "", day_of_week: "monday", day_of_month: 1, time_of_day: "09:00", sent_history: [], batches: ["all"] })),
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
      setSentHistory(digest.sent_history || []);

      // Get email from auth if digest email is empty
      const supabase = getBrowserClient();
      if (!digest.email) {
        const { data } = await supabase.auth.getSession();
        if (data.session?.user?.email) {
          setDigestEmail(data.session.user.email);
        }
      }

      // Fetch active resume from Supabase database
      try {
        const { data: resumes } = await supabase
          .from("resumes")
          .select("filename")
          .eq("is_active", true)
          .maybeSingle();
        if (resumes) {
          setActiveResume(resumes.filename);
        }
      } catch (err) {
        console.error("Failed to fetch active resume:", err);
      }
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

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      await Promise.all([
        updateProfile({
          name,
          current_role: currentRole,
          core_skills: skills,
          years_experience: yearsExperience,
        }),
        updateDigestPreferences({
          enabled: digestFrequency !== "never",
          frequency: digestFrequency,
          email: digestEmail,
          day_of_week: digestDayOfWeek,
          day_of_month: digestDayOfMonth,
          time_of_day: digestTimeOfDay,
          batches: digestBatches,
        }),
      ]);

      // Upload resume if selected
      if (resumeFile) {
        const formData = new FormData();
        formData.append("file", resumeFile);
        const supabase = getBrowserClient();
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;
        const res = await fetch(`${API_BASE}/api/resume/upload`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        });
        if (!res.ok) throw new Error("Resume upload failed");
        setActiveResume(resumeFile.name);
        setResumeFile(null);
      }

      setMessage("Settings saved successfully.");
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : "Save failed"}`);
    } finally {
      setSaving(false);
    }
  };

  const runningItem = sentHistory.find((x) => x.startsWith("RUNNING:"));
  const progressText = runningItem ? runningItem.replace("RUNNING:", "") : "";

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
        Manage your profile, email digest, and resume.
      </p>

      <div className="space-y-6">
        {/* Profile Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Profile</h2>
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
                  <button
                    onClick={() => removeSkill(i)}
                    className="ml-0.5 text-indigo-400 hover:text-white"
                  >
                    &times;
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Email Digest Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Email Digest</h2>
              <p className="text-xs text-gray-500">Automated scheduler preferences</p>
            </div>
            {digestFrequency !== "never" && (
              <button
                onClick={async () => {
                  setSending(true);
                  setSendResult("");
                  setSendError(false);
                  try {
                    const res = await sendDigestNow(digestEmail);
                    setSendResult(res.message);
                    const isMsgError = res.message.toLowerCase().includes("fail") || 
                                       res.message.toLowerCase().includes("error") || 
                                       res.message.toLowerCase().includes("limit") || 
                                       res.message.toLowerCase().includes("unauthorized") ||
                                       !res.sent;
                    if (isMsgError) {
                      setSendError(true);
                    }
                    // Immediately fetch latest preferences to capture RUNNING token
                    const d = await getDigestPreferences().catch(() => null);
                    if (d) {
                      setSentHistory(d.sent_history || []);
                    }
                  } catch (err) {
                    setSendResult(err instanceof Error ? err.message : "Failed to send digest");
                    setSendError(true);
                  } finally {
                    setSending(false);
                  }
                }}
                disabled={sending || sentHistory.some((x) => x.startsWith("RUNNING:"))}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {sending || sentHistory.some((x) => x.startsWith("RUNNING:")) ? "Scanning..." : "Send Now"}
              </button>
            )}
          </div>

          {(sending || sentHistory.some((x) => x.startsWith("RUNNING:"))) && (
            <div className="mb-4 rounded-xl border border-indigo-500/30 bg-indigo-950/30 p-4 shadow-lg shadow-indigo-500/5">
              <div className="flex gap-3 items-start">
                <span className="text-xl animate-spin shrink-0">⏳</span>
                <div className="text-xs text-indigo-200 leading-relaxed w-full">
                  <span className="font-bold text-indigo-400 block mb-1 uppercase tracking-wider text-[10px]">Deep Digest Scan in Progress</span>
                  
                  {progressText ? (
                    <div className="mb-3 p-2.5 rounded-lg bg-indigo-950/80 border border-indigo-500/20 text-indigo-300 font-medium flex items-center gap-2">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                      </span>
                      <span>Live Scraper Status: <span className="text-white font-bold">{progressText}</span></span>
                    </div>
                  ) : (
                    <div className="mb-3 p-2.5 rounded-lg bg-indigo-950/80 border border-indigo-500/20 text-indigo-300 font-medium flex items-center gap-2">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                      </span>
                      <span>Live Scraper Status: <span className="text-white font-bold">Initializing background search...</span></span>
                    </div>
                  )}

                  Our automated backend scraper is initiating a comprehensive search across 250+ companies and multiple global ATS platforms. 
                  Because this is an extremely thorough, anti-bot-bypassing background task matching against your unique profile, 
                  <strong>it will take approximately 3-4 hours to complete</strong>. 
                  <span className="block mt-2 text-gray-400">
                    You do not need to keep this tab open! Once completed, all scored matching jobs will be compiled and sent directly to your inbox at <strong className="text-white font-semibold">{digestEmail || "your registered email"}</strong>.
                  </span>
                </div>
              </div>
            </div>
          )}

          {sendResult && (
            <p className={`mb-4 text-xs font-semibold ${sendError || sendResult.toLowerCase().includes("fail") || sendResult.toLowerCase().includes("error") || sendResult.toLowerCase().includes("limit") ? "text-red-400" : "text-emerald-400"}`}>
              {sendResult}
            </p>
          )}

          <div className="space-y-4">
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
                <label className="block text-sm text-gray-400 mb-1">Send on Day</label>
                <select
                  value={digestDayOfWeek}
                  onChange={(e) => setDigestDayOfWeek(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none capitalize"
                >
                  <option value="monday">Monday</option>
                  <option value="tuesday">Tuesday</option>
                  <option value="wednesday">Wednesday</option>
                  <option value="thursday">Thursday</option>
                  <option value="friday">Friday</option>
                  <option value="saturday">Saturday</option>
                  <option value="sunday">Sunday</option>
                </select>
              </div>
            )}

            {digestFrequency === "monthly" && (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Send on Day of Month</label>
                <select
                  value={digestDayOfMonth}
                  onChange={(e) => setDigestDayOfMonth(Number(e.target.value))}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                    <option key={day} value={day}>
                      Day {day}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {digestFrequency === "daily" && (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Send at Time</label>
                <select
                  value={digestTimeOfDay}
                  onChange={(e) => setDigestTimeOfDay(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  {Array.from({ length: 24 }, (_, i) => {
                    const hour = String(i).padStart(2, "0");
                    return `${hour}:00`;
                  }).map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm text-gray-400 mb-1">Email Address</label>
              <input
                type="email"
                value={digestEmail}
                onChange={(e) => setDigestEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                placeholder="you@example.com"
              />
            </div>

            <div className="col-span-1 sm:col-span-2 pt-3 border-t border-gray-800">
              <label className="block text-sm font-semibold text-gray-300 mb-2">
                Included Scraper Batches in Email Digest
              </label>
              <p className="text-xs text-gray-500 mb-3">
                Choose which regions/boards you want the automated scheduler to scan for your matches.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { id: "all", label: "All Regions (Complete Master Scan)" },
                  { id: "india", label: "India boards & company career pages" },
                  { id: "europe_companies", label: "Europe company career pages (e.g. ASML, Adyen)" },
                  { id: "europe_boards", label: "Europe job boards (IamExpat, TogetherAbroad, Arbeitnow)" },
                  { id: "middle_east", label: "Middle East job boards & company careers" },
                  { id: "apac", label: "APAC job boards & company careers" },
                  { id: "us_canada", label: "US & Canada job boards & company careers" },
                  { id: "remote", label: "Global Remote boards (WeWorkRemotely, Remotive)" },
                 ].map((batch) => {
                  const isChecked = digestBatches.includes(batch.id);

                  return (
                    <label
                      key={batch.id}
                      className="inline-flex items-start gap-2.5 text-sm cursor-pointer text-gray-300 hover:text-white"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (batch.id === "all") {
                            if (e.target.checked) {
                              setDigestBatches(["all"]);
                            } else {
                              setDigestBatches([]);
                            }
                          } else {
                            let updated = [...digestBatches];
                            if (updated.includes("all")) {
                              updated = updated.filter((x) => x !== "all");
                            }
                            if (e.target.checked) {
                              updated.push(batch.id);
                            } else {
                              updated = updated.filter((x) => x !== batch.id);
                            }
                            if (updated.length === 0) {
                              updated = ["all"];
                            }
                            setDigestBatches(updated);
                          }
                        }}
                        className="rounded border-gray-700 bg-gray-800 text-indigo-600 focus:ring-indigo-500 mt-1"
                      />
                      <span>{batch.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Resume Section */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Resume</h2>
          {activeResume && (
            <p className="text-sm text-gray-400 mb-3">
              Active resume: <span className="text-white">{activeResume}</span>
            </p>
          )}
          <label className="block">
            <span className="text-sm text-gray-400 mb-1 block">Upload PDF</span>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-400 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-500 file:cursor-pointer"
            />
          </label>
          {resumeFile && (
            <p className="text-xs text-gray-500 mt-2">
              Selected: {resumeFile.name}
            </p>
          )}
        </div>

        {/* Save */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {message && (
            <p
              className={`text-sm ${
                message.startsWith("Error") ? "text-red-400" : "text-emerald-400"
              }`}
            >
              {message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
