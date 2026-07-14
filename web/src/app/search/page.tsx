"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { searchJobs, addToTracker, getProfile, type JobResult } from "@/lib/api";

export default function SearchPage() {
  const router = useRouter();
  const [hasResume, setHasResume] = useState<boolean | null>(null);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("Remote");
  const [threshold, setThreshold] = useState(65);
  const [requireVisa, setRequireVisa] = useState(true);
  const [jobType, setJobType] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [skills, setSkills] = useState("");
  const [excludeCompanies, setExcludeCompanies] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<JobResult[]>([]);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [tracked, setTracked] = useState<Set<string>>(new Set());

  const getTargetedBoards = () => {
    const locLower = (location || "").toLowerCase();
    const isRemote = workMode === "remote" || locLower.includes("remote");
    const isIndia = locLower.includes("india") || ["pune", "mumbai", "bangalore", "bengaluru", "hyderabad", "chennai", "delhi", "noida", "gurgaon"].some(city => locLower.includes(city));

    if (isRemote) {
      return "WeWorkRemotely, Remotive, and LinkedIn";
    }
    if (isIndia) {
      return "Naukri, Instahyre, and LinkedIn";
    }
    return "LinkedIn, Indeed, and Glassdoor";
  };

  useEffect(() => {
    getProfile()
      .then((p) => setHasResume(!!p.core_skills?.length))
      .catch(() => setHasResume(false));
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() && !hasResume) return;
    setLoading(true);
    setError("");
    setSearched(true);
    try {
      const locList = location.split(",").map((l) => l.trim()).filter(Boolean);
      const primaryLoc = locList[0] || "Remote";

      const res = await searchJobs({
        query: query.trim(),
        location: primaryLoc,
        threshold,
        max_results: 20,
        require_visa: requireVisa,
        job_type: jobType,
        work_mode: workMode,
        locations: locList,
        skills: skills.trim() ? skills.split(",").map((s) => s.trim()).filter(Boolean) : [],
        exclude_companies: excludeCompanies.trim() ? excludeCompanies.split(",").map((s) => s.trim()).filter(Boolean) : [],
        sources: selectedSources,
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
        <p className="text-gray-400 text-sm mb-4">
          Search top job boards and targeted company channels on-demand. Results are scored against your profile.
        </p>
        <form onSubmit={handleSearch} className="space-y-4">
          <div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. backend engineer, senior java developer"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5 space-y-3">
            <label className="text-sm font-semibold text-gray-300 flex items-center gap-1.5">
              <span>🎯</span> Select Job Boards to Scan (Max 4 — Defaults to auto-targeted boards based on location)
            </label>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {["LinkedIn", "Indeed", "Naukri", "Instahyre", "WeWorkRemotely", "Remotive", "Arbeitnow", "IamExpat", "TogetherAbroad", "FoundIt", "TimesJobs"].map((source) => {
                const isChecked = selectedSources.includes(source);
                const isDisabled = !isChecked && selectedSources.length >= 4;
                return (
                  <label
                    key={source}
                    className={`inline-flex items-center gap-2 text-sm cursor-pointer ${
                      isDisabled ? "opacity-35 cursor-not-allowed" : "hover:text-white"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isDisabled}
                      onChange={(e) => {
                        if (e.target.checked) {
                          if (selectedSources.length < 4) {
                            setSelectedSources([...selectedSources, source]);
                          }
                        } else {
                          setSelectedSources(selectedSources.filter((s) => s !== source));
                        }
                      }}
                      className="rounded border-gray-700 bg-gray-800 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-gray-900"
                    />
                    <span className={isChecked ? "text-indigo-400 font-semibold" : "text-gray-300"}>
                      {source}
                    </span>
                  </label>
                );
              })}
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
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {showFilters ? "Hide filters" : "More filters"}
            </button>
            <button
              type="submit"
              disabled={loading || (!query.trim() && !hasResume)}
              className="rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
          {showFilters && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-2 border-t border-gray-800">
              <div className="flex items-center gap-3">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={requireVisa}
                    onChange={(e) => setRequireVisa(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:bg-indigo-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"></div>
                </label>
                <span className="text-sm text-gray-300">Require visa/relo</span>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Location</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. Remote, India, Berlin"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Job type</label>
                <select
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="">Any</option>
                  <option value="full-time">Full-time</option>
                  <option value="contract">Contract</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Work mode</label>
                <select
                  value={workMode}
                  onChange={(e) => setWorkMode(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="">Any</option>
                  <option value="remote">Remote</option>
                  <option value="on-site">On-site</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Skills filter (comma-separated)</label>
                <input
                  type="text"
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  placeholder="e.g. rust, kubernetes"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Exclude companies (comma-separated)</label>
                <input
                  type="text"
                  value={excludeCompanies}
                  onChange={(e) => setExcludeCompanies(e.target.value)}
                  placeholder="e.g. acme corp, mollie"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>
          )}
        </form>
      </div>

      <div className="bg-indigo-950/20 border border-indigo-900/40 rounded-lg p-3.5 mb-6 flex items-start gap-3">
        <span className="text-indigo-400 mt-0.5">ℹ️</span>
        <div className="text-xs text-gray-400 leading-relaxed">
          <span className="text-indigo-300 font-semibold">Note:</span> This live search retrieves on-demand results directly from your selected 
          job boards. High-latency, heavy company career page scraping is skipped here to ensure sub-10s response times, 
          but is covered extensively in your scheduled <span className="text-white font-semibold">Daily/Weekly Email Digests</span>!
        </div>
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
          {/* Email Digest Upsell Banner */}
          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-5 py-4 mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm">
            <div className="space-y-1">
              <p className="font-semibold text-indigo-400">💡 Want more matched opportunities?</p>
              <p className="text-gray-400 text-xs leading-relaxed">
                Lightweight web searches show up to 20 top matches. To automatically scan across 250+ company career pages and get all matching roles delivered straight to your inbox daily or weekly, set up your Email Digest!
              </p>
            </div>
            <Link
              href="/settings"
              className="shrink-0 rounded-lg bg-indigo-600/20 border border-indigo-500/30 px-4 py-2 font-semibold text-indigo-400 hover:bg-indigo-600/30 transition-colors text-center text-xs"
            >
              Configure Digest &rarr;
            </Link>
          </div>

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
