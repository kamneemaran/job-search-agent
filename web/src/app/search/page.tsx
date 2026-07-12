"use client";

import { useState } from "react";
import { searchJobs, type JobResult } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("Remote");
  const [threshold, setThreshold] = useState(65);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<JobResult[]>([]);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

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

  const scoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-400 bg-emerald-400/10";
    if (score >= 65) return "text-yellow-400 bg-yellow-400/10";
    return "text-gray-400 bg-gray-400/10";
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      {/* Search Form */}
      <div className="rounded-2xl border border-gray-800 bg-gray-900/50 p-8 mb-10">
        <h1 className="text-3xl font-bold mb-2">Job Search</h1>
        <p className="text-gray-400 text-sm mb-8">
          Search across 250+ company ATS and 15+ job boards. Results scored against your profile.
        </p>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Job title or skills
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. backend engineer, senior java developer"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Location
              </label>
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

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 mb-6 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {searched && !loading && results.length === 0 && !error && (
        <div className="text-center py-16 text-gray-500">
          No jobs found matching your criteria. Try lowering the threshold or changing your query.
        </div>
      )}

      {results.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              {results.length} matches found
            </h2>
            <span className="text-sm text-gray-500">
              Sorted by score
            </span>
          </div>
          <div className="space-y-3">
            {results.map((job, i) => (
              <div
                key={`${job.company}-${job.title}-${i}`}
                className="rounded-xl border border-gray-800 bg-gray-900/50 p-5 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-semibold text-white truncate">
                        {job.title}
                      </h3>
                      <span
                        className={`flex-shrink-0 rounded-md px-2.5 py-0.5 text-sm font-bold ${scoreColor(
                          job.score
                        )}`}
                      >
                        {job.score}
                      </span>
                    </div>
                    <div className="text-sm text-gray-400 mb-2">
                      {job.company}
                      {job.location && ` · ${job.location}`}
                      {job.salary && (
                        <span className="ml-2 text-emerald-400">
                          {job.salary}
                        </span>
                      )}
                    </div>
                    {job.note && (
                      <p className="text-xs text-gray-500 mb-2">{job.note}</p>
                    )}
                    {job.description && (
                      <p className="text-xs text-gray-500 line-clamp-2">
                        {job.description}
                      </p>
                    )}
                  </div>
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 rounded-lg border border-gray-700 px-3 py-2 text-xs font-medium text-gray-300 hover:bg-gray-800 transition-colors"
                    >
                      Apply &rarr;
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
