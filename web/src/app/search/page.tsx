"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { searchJobs, addToTracker, getProfile, type JobResult } from "@/lib/api";

export default function SearchPage() {
  const router = useRouter();
  const [hasResume, setHasResume] = useState<boolean | null>(null);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [threshold, setThreshold] = useState(65);
  const [requireVisa, setRequireVisa] = useState(false);
  const [jobType, setJobType] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [skills, setSkills] = useState("");
  const [excludeCompanies, setExcludeCompanies] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("Remote");
  const [showFilters, setShowFilters] = useState(false);
  const [postedDateFilter, setPostedDateFilter] = useState("any");
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

  const CATEGORY_MAP: Record<string, string[]> = {
    "Remote": ["WeWorkRemotely", "Remotive", "LinkedIn", "RemoteOK", "Himalayas", "NoDesk", "WorkAtStartup", "ArcDev", "WorkingNomads"],
    "India": ["Naukri", "Instahyre", "FoundIt", "TimesJobs", "Indeed"],
    "Europe": ["Arbeitnow", "IamExpat", "TogetherAbroad", "EURES", "StepStone", "InfoJobs", "Bundesagentur", "WelcomeToNL", "WorkInFinland", "WorkInLux"],
    "Global": ["LinkedIn", "Indeed", "Glassdoor", "VisaSponsor"]
  };

  const handleSelectCategory = (catName: string) => {
    const boards = CATEGORY_MAP[catName] || [];
    // Select first 5 boards from this category
    const toSelect = boards.slice(0, 5);
    setSelectedSources(toSelect);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() && !hasResume) return;
    setLoading(true);
    setError("");
    setSearched(true);
    try {
      const locList = location.split(",").map((l) => l.trim()).filter(Boolean);
      const primaryLoc = locList[0] || "";

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
        posted_date_filter: postedDateFilter,
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
        posted_date: job.posted_date,
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

          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <label className="text-sm font-semibold text-gray-300 flex items-center gap-1.5">
                <span>🎯</span> Scan Channels (Max 5 — Defaults to auto-targeted boards)
              </label>
              <div className="flex flex-wrap items-center gap-1">
                {Object.keys(CATEGORY_MAP).map((catName) => (
                  <button
                    key={catName}
                    type="button"
                    onClick={() => setActiveCategory(catName)}
                    className={`rounded px-2.5 py-1 text-xs font-semibold border transition-all cursor-pointer ${
                      activeCategory === catName
                        ? "bg-indigo-600 border-indigo-500 text-white shadow-md shadow-indigo-600/20"
                        : "bg-gray-850 hover:bg-gray-800 border-gray-800 text-gray-400 hover:text-white"
                    }`}
                  >
                    {catName}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-gray-800 bg-gray-950/25 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between border-b border-gray-850 pb-1.5">
                <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">{activeCategory} Channels</span>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => handleSelectCategory(activeCategory)}
                    className="text-[11px] font-semibold text-indigo-300 hover:text-indigo-200 hover:underline cursor-pointer"
                  >
                    Select All in {activeCategory}
                  </button>
                  <span className="text-gray-700 text-xs">|</span>
                  <button
                    type="button"
                    onClick={() => setSelectedSources([])}
                    className="text-[11px] font-semibold text-gray-400 hover:text-gray-200 hover:underline cursor-pointer"
                  >
                    Clear All ({selectedSources.length})
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {CATEGORY_MAP[activeCategory].map((source) => {
                  const isChecked = selectedSources.includes(source);
                  const isDisabled = !isChecked && selectedSources.length >= 5;
                  return (
                    <label
                      key={source}
                      className={`inline-flex items-center gap-1.5 text-xs cursor-pointer ${
                        isDisabled ? "opacity-35 cursor-not-allowed" : "hover:text-white"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={isDisabled}
                        onChange={(e) => {
                          if (e.target.checked) {
                            if (selectedSources.length < 5) {
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
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2 border-t border-gray-800">
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
                <label className="text-xs text-gray-500 mb-1 block">Job Age Filter</label>
                <select
                  value={postedDateFilter}
                  onChange={(e) => setPostedDateFilter(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none cursor-pointer"
                >
                  <option value="any">Any Time</option>
                  <option value="1d">Last 24 Hours</option>
                  <option value="1w">Last 1 Week</option>
                  <option value="1m">Last 1 Month</option>
                  <option value="3m">Last 3 Months</option>
                </select>
              </div>
            </div>
          )}
        </form>
      </div>

      <div className="bg-gradient-to-r from-indigo-950/40 via-purple-950/30 to-indigo-950/40 border border-indigo-500/30 rounded-xl p-4.5 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg shadow-indigo-500/5">
        <div className="flex items-start gap-3 flex-1">
          <span className="text-xl shrink-0">💡</span>
          <div className="text-xs text-gray-300 leading-relaxed">
            <span className="text-indigo-400 font-bold uppercase tracking-wider text-[10px] block mb-0.5">Maximize Your Job Search</span>
            On-demand search scans selected boards instantly. High-latency, heavy automated company career page scraping (over 250+ domains!) is handled in the background to ensure sub-10s speeds, and is delivered daily/weekly via your <span className="text-white font-semibold underline decoration-indigo-400">Email Digest</span>!
          </div>
        </div>
        <Link
          href="/settings"
          className="shrink-0 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 hover:shadow-md hover:shadow-indigo-500/20 transition-all text-center"
        >
          Configure Email Digest &rarr;
        </Link>
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
              
              const detectJobType = () => {
                const text = `${job.title} ${job.description} ${job.note}`.toLowerCase();
                if (text.includes("full-time") || text.includes("full time")) return "Full-time";
                if (text.includes("contract") || text.includes("contractor") || text.includes("freelance")) return "Contract";
                if (text.includes("part-time") || text.includes("part time")) return "Part-time";
                if (text.includes("internship") || text.includes("intern")) return "Internship";
                return null;
              };
              const jobTypeBadge = detectJobType();

              return (
                <div key={key + i} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5 hover:border-gray-700 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-semibold text-white truncate">{job.title}</h3>
                        <span className={`flex-shrink-0 rounded-md px-2.5 py-0.5 text-sm font-bold ${scoreColor(job.score)}`}>{job.score}</span>
                      </div>
                      <div className="text-sm text-gray-400 mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span>{job.company}</span>
                        {job.location && <span>· {job.location}</span>}
                        {job.posted_date && <span>· Posted {job.posted_date}</span>}
                        {jobTypeBadge && (
                          <span className="inline-block rounded bg-gray-800 border border-gray-700/60 px-1.5 py-0.5 text-[10px] font-medium text-indigo-400 uppercase tracking-wider">
                            {jobTypeBadge}
                          </span>
                        )}
                        {job.salary && <span className="text-emerald-400">· {job.salary}</span>}
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
