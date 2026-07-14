"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { searchJobs, addToTracker, getProfile, type JobResult } from "@/lib/api";

export default function SearchPage() {
  const router = useRouter();
  const [hasResume, setHasResume] = useState<boolean | null>(null);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("Remote");
  const [threshold, setThreshold] = useState(65);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<JobResult[]>([]);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [tracked, setTracked] = useState<Set<string>>(new Set());

  useEffect(() => {
    getProfile()
      .then((p) => setHasResume(!!p.core_skills?.length))
      .catch(() => setHasResume(false));
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setSearched(true);
    try {
      const res = await searchJobs({
        query: query.trim(),
        location,
        threshold,
        max_results: 20,
      });
      setResults(res.jobs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAddToTracker = async (job: JobResult) => {
    const key = `${job.company}|${job.title}`;
    try {
      await addToTracker({
        title: job.title,
        company: job.company,
        url: job.url,
        score: job.score,
        description: job.description,
        salary: job.salary || "",
        location: job.location,
      });
      setTracked((prev) => new Set(prev).add(key));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("409") || msg.includes("already")) {
        setTracked((prev) => new Set(prev).add(key));
      } else {
        alert("Failed to add to tracker: " + msg);
      }
    }
  };

  const scoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-400 bg-emerald-400/10";
    if (score >= 65) return "text-yellow-400 bg-yellow-400/10";
    return "text-gray-400 bg-gray-400/10";
  };

  // Resume check
  if (hasResume === null) {
    return <div className="mx-auto max-w-5xl px-4 py-12"><div className="text-center py-16 text-gray-500">Loading...</div></div>;
  }

  if (hasResume === false) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="rounded-2xl border border-indigo-800 bg-indigo-900/20 p-12 text-center max-w-lg mx-auto">
          <div className="text-5xl mb-4">📄</div>
          <h1 className="text-2xl font-bold mb-3">Upload Your Resume First</h1>
          <p className="text-gray-400 mb-8">
            We need your resume to analyze your skills and experience before we can find matching jobs.
          </p>
          <button
            onClick={() => router.push("/resume")}
            className="rounded-lg bg-indigo-600 px-8 py-3 font-semibold text-white hover:bg-indigo-500"
          >
            Upload Resume
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      {/* Search Form */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 mb-10">
        <h1 className="text-3xl font-bold mb-2">Job Search</h1>
        <p className="text-gray-400 text-sm mb-8">
          Search across job boards and company career pages. Results scored against your profile.
        </p>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. backend engineer, senior java developer"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Remote"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400">Min score:</label>
              <input
                type="range"
                min={0}
                max={100}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-32 accent-indigo-500"
              />
              <span className="text-sm font-mono text-indigo-400 w-8">{threshold}</span>
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 mb-6 text-red-400 text-sm">{error}</div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 mb-6">
          <div className="relative w-16 h-16 mb-4">
            <div className="absolute inset-0 rounded-full border-4 border-gray-700"></div>
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-indigo-500 animate-spin"></div>
          </div>
          <p className="text-gray-400 text-sm">Searching job boards and company career pages...</p>
          <p className="text-gray-600 text-xs mt-1">This may take up to 30 seconds</p>
        </div>
      )}

      {searched && !loading && results.length === 0 && !error && (
        <div className="text-center py-16 text-gray-500">
          No jobs found matching your criteria. Try lowering the threshold or changing your query.
        </div>
      )}

      {results.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">{results.length} matches found</h2>
            <span className="text-sm text-gray-500">Sorted by score</span>
          </div>
          <div className="space-y-3">
            {results.map((job, i) => {
              const key = `${job.company}|${job.title}`;
              const isTracked = tracked.has(key);
              return (
                <div key={key + i} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5 hover:border-gray-700 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold text-white truncate">{job.title}</h3>
                        <span className={`flex-shrink-0 rounded-md px-2.5 py-0.5 text-sm font-bold ${scoreColor(job.score)}`}>{job.score}</span>
                      </div>
                      <div className="text-sm text-gray-400 mb-2">
                        {job.company}
                        {job.location && ` · ${job.location}`}
                        {job.salary && <span className="ml-2 text-emerald-400">{job.salary}</span>}
                      </div>
                      {job.note && <p className="text-xs text-gray-500 mb-2">{job.note}</p>}
                      {job.description && <p className="text-xs text-gray-500 line-clamp-2">{job.description}</p>}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleAddToTracker(job)}
                        disabled={isTracked}
                        className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${isTracked ? "bg-emerald-600/20 border border-emerald-600/30 text-emerald-400 cursor-default" : "bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700"}`}
                      >
                        {isTracked ? "✓ Tracked" : "+ Track"}
                      </button>
                      {job.url && (
                        <a href={job.url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-gray-700 px-3 py-2 text-xs font-medium text-gray-300 hover:bg-gray-800 transition-colors">
                          Apply &rarr;
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
