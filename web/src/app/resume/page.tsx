"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getBrowserClient } from "@/lib/supabase/client";
import { updateProfile } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ResumePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [parsed, setParsed] = useState<{
    name: string;
    current_role: string;
    core_skills: string[];
    years_experience: number;
  } | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");

    try {
      const supabase = getBrowserClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session?.session?.access_token;
      if (!token) throw new Error("Not signed in");

      // Upload and parse resume
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

      // Auto-save profile from parsed resume
      await updateProfile({
        name: data.name || "",
        current_role: data.current_role || "",
        core_skills: data.core_skills || [],
        years_experience: data.years_experience || 0,
      });

      setParsed({
        name: data.name,
        current_role: data.current_role,
        core_skills: data.core_skills,
        years_experience: data.years_experience,
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (success && parsed) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="w-full max-w-md text-center">
          <div className="text-5xl mb-4">✅</div>
          <h1 className="text-2xl font-bold mb-2">Resume Parsed!</h1>
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 text-left space-y-2 mb-8">
            <p className="text-sm"><span className="text-gray-500">Name:</span> <span className="text-white">{parsed.name}</span></p>
            <p className="text-sm"><span className="text-gray-500">Role:</span> <span className="text-white">{parsed.current_role}</span></p>
            <p className="text-sm"><span className="text-gray-500">Experience:</span> <span className="text-white">{parsed.years_experience} years</span></p>
            <div className="text-sm">
              <span className="text-gray-500">Skills:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {parsed.core_skills.slice(0, 8).map((s, i) => (
                  <span key={i} className="rounded-md bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 text-xs text-indigo-400">{s}</span>
                ))}
                {parsed.core_skills.length > 8 && (
                  <span className="text-xs text-gray-500">+{parsed.core_skills.length - 8} more</span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={() => router.push("/search")}
            className="rounded-lg bg-indigo-600 px-8 py-3 font-semibold text-white hover:bg-indigo-500"
          >
            Start Job Search
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Upload Your Resume</h1>
          <p className="text-gray-400">
            We&apos;ll parse your skills, experience, and role to find the best job matches.
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

        {error && (
          <div className="mt-4 rounded-lg bg-red-900/20 border border-red-800 p-3 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
