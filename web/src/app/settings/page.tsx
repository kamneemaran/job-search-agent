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
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState("");

  // Resume state
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [activeResume, setActiveResume] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const [profile, digest] = await Promise.all([
        getProfile(),
        getDigestPreferences().catch(() => ({ enabled: false, frequency: "weekly", email: "", day_of_week: "monday", day_of_month: 1, time_of_day: "09:00", sent_history: [] })),
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
                  try {
                    const res = await sendDigestNow(digestEmail);
                    setSendResult(res.message);
                  } catch (err) {
                    setSendResult(err instanceof Error ? err.message : "Failed to send digest");
                  } finally {
                    setSending(false);
                  }
                }}
                disabled={sending}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {sending ? "Sending..." : "Send Now"}
              </button>
            )}
          </div>

          {sendResult && (
            <p className={`mb-4 text-xs ${sendResult.includes("Limit") || sendResult.includes("limit") || sendResult.includes("Error") ? "text-red-400" : "text-emerald-400"}`}>
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
