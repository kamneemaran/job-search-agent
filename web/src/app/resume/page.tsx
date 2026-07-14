"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getBrowserClient } from "@/lib/supabase/client";
import { getProfile, updateProfile, type Profile } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ResumePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [existing, setExisting] = useState<Profile | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [parsed, setParsed] = useState<{
    name: string;
    current_role: string;
    core_skills: string[];
    years_experience: number;
  } | null>(null);

  useEffect(() => {
    getProfile()
      .then((p) => {
        if (p.core_skills?.length > 0) {
          setExisting(p);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");

    try {
      const supabase = getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) throw new Error("Not signed in");

      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/resume/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();

      await updateProfile({
        name: data.name || "",
        current_role: data.current_role || "",
        core_skills: data.core_skills || [],
        years_experience: data.years_experience || 0,
      });

      const profile: Profile = {
        name: data.name,
        current_role: data.current_role,
        core_skills: data.core_skills,
        years_experience: data.years_experience,
        seniority_keywords: [],
      };
      setParsed(data);
      setExisting(profile);
      setShowUpload(false);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="text-center py-16 text-gray-500">Loading...</div>
      </div>
    );
  }

  // Show existing resume profile
  if (existing && !showUpload) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="w-full max-w-lg">
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold mb-2">Your Resume</h1>
            <p className="text-gray-400 text-sm">
              {parsed ? "Resume uploaded and parsed successfully." : "Your current profile from your uploaded resume."}
            </p>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 space-y-4 mb-6">
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Name</span>
              <p className="text-white font-medium">{existing.name || "N/A"}</p>
            </div>
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Current Role</span>
              <p className="text-white font-medium">{existing.current_role || "N/A"}</p>
            </div>
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Experience</span>
              <p className="text-white font-medium">{existing.years_experience} years</p>
            </div>
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Skills</span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {existing.core_skills.slice(0, 12).map((s, i) => (
                  <span
                    key={i}
                    className="rounded-md bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 text-xs text-indigo-400"
                  >
                    {s}
                  </span>
                ))}
                {existing.core_skills.length > 12 && (
                  <span className="text-xs text-gray-500">+{existing.core_skills.length - 12} more</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setShowUpload(true)}
              className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-6 py-3 font-semibold text-gray-300 hover:bg-gray-700 transition-colors"
            >
              Replace Resume
            </button>
            <button
              onClick={() => router.push("/search")}
              className="flex-1 rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              Search Jobs
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Upload form (no resume yet, or user clicked Replace)
  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">
            {existing ? "Replace Your Resume" : "Upload Your Resume"}
          </h1>
          <p className="text-gray-400">
            {existing
              ? "Upload a new PDF to update your profile and skills."
              : "We'll parse your skills, experience, and role to find the best job matches."}
          </p>
        </div>

        <div className="rounded-2xl border border-dashed border-gray-700 bg-gray-900/50 p-12 text-center">
          <div className="text-4xl mb-4">📄</div>
          <label className="block cursor-pointer">
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />
            <div className="rounded-lg border border-gray-700 bg-gray-800 px-6 py-4 text-sm text-gray-300 hover:bg-gray-700 transition-colors">
              {file ? file.name : "Click to select PDF resume"}
            </div>
          </label>
          {file && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="mt-6 rounded-lg bg-indigo-600 px-8 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors w-full"
            >
              {uploading ? "Parsing..." : "Upload & Analyze"}
            </button>
          )}
        </div>

        {existing && (
          <button
            onClick={() => setShowUpload(false)}
            className="mt-4 w-full text-center text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            Cancel and go back
          </button>
        )}

        {error && (
          <div className="mt-4 rounded-lg bg-red-900/20 border border-red-800 p-3 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
