"use client";

import Link from "next/link";

export default function GuidePage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-extrabold text-white mb-3">JobPilot User Guide</h1>
        <p className="text-gray-400 text-lg">
          Master the AI-powered job search engine and automate your matching workflow.
        </p>
      </div>

      <div className="space-y-10">
        {/* Section 1 */}
        <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-8">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xl text-indigo-400 font-bold border border-indigo-500/20">1</span>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-white">Upload and Parse Your Resume</h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                Before searching, navigate to the <Link href="/resume" className="text-indigo-400 hover:underline">Resume</Link> page and upload your PDF resume. JobPilot's backend parser will instantly analyze your resume to extract:
              </p>
              <ul className="list-disc pl-5 text-gray-400 text-sm space-y-1">
                <li>Your full name and current job title.</li>
                <li>Your total years of professional experience (used for seniority matching).</li>
                <li>A comprehensive list of core technical skills.</li>
              </ul>
              <p className="text-gray-500 text-xs mt-2 italic">
                Note: Once uploaded, your profile persists. You will never need to re-upload unless you click the "Replace Resume" button to update your skills.
              </p>
            </div>
          </div>
        </section>

        {/* Section 2 */}
        <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-8">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xl text-indigo-400 font-bold border border-indigo-500/20">2</span>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-white">How Job Scoring Works</h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                JobPilot doesn't just search; it grades every single listing against your personal profile on a scale of **0–100**:
              </p>
              <ul className="list-disc pl-5 text-gray-400 text-sm space-y-1">
                <li><strong className="text-white">Skill Overlap:</strong> Evaluates how well your resume's skills match the Job Description.</li>
                <li><strong className="text-white">Seniority Verification:</strong> Cross-checks experience requirements. If a job is too senior (or too junior) for your profile, it is filtered out.</li>
                <li><strong className="text-white">Domestic vs International Visa Check:</strong> For jobs based outside of India, JobPilot scans for active visa sponsorship signals (either in the description, known sponsor lists, or the career page). If no signal is found and you have the "Require visa" filter enabled, the job is scored 0 and filtered out.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section 3 */}
        <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-8">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xl text-indigo-400 font-bold border border-indigo-500/20">3</span>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-white">Run Searches and Apply Advanced Filters</h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                Go to the <Link href="/search" className="text-indigo-400 hover:underline">Search</Link> page, type a query (like *"backend engineer"*), and hit search. JobPilot searches across multiple job boards (LinkedIn, Indeed, Naukri, Glassdoor) and company ATS engines.
              </p>
              <p className="text-gray-400 text-sm leading-relaxed">
                Click **"More filters"** to expand the form and customize your search:
              </p>
              <ul className="list-disc pl-5 text-gray-400 text-sm space-y-1">
                <li><strong className="text-white">Require visa/relo:</strong> Check this to auto-filter out international roles that do not offer visa sponsorship. Turn it OFF to see all available remote roles globally.</li>
                <li><strong className="text-white">Job Type:</strong> Filter specifically for Full-time or Contract/Freelance roles.</li>
                <li><strong className="text-white">Work Mode:</strong> Select Remote, Hybrid, or On-site.</li>
                <li><strong className="text-white">Skills:</strong> Enter a comma-separated list of additional keywords to require in the job listings.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Section 4 */}
        <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-8">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xl text-indigo-400 font-bold border border-indigo-500/20">4</span>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-white">Automate Your Scan with Email Digest</h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                Tired of searching manually? Go to the <Link href="/settings" className="text-indigo-400 hover:underline">Settings</Link> page and configure your Email Digest:
              </p>
              <ul className="list-disc pl-5 text-gray-400 text-sm space-y-1">
                <li><strong className="text-white">Frequency:</strong> Choose Daily, Weekly, or Monthly.</li>
                <li><strong className="text-white">Scheduled Time:</strong> Choose the exact hour, day of the week, or day of the month when your digest should be compiled and sent to your inbox.</li>
                <li><strong className="text-white">Send Now (On-Demand):</strong> Want an instant update? Click the "Send Now" button. It will run a fresh background scan and email you the top matching jobs within 1–2 minutes.</li>
              </ul>
              <p className="text-gray-500 text-xs mt-2 italic">
                Note: On-demand "Send Now" requests are limited to once every 8 hours to protect your API quotas.
              </p>
            </div>
          </div>
        </section>
      </div>

      <div className="text-center mt-12">
        <Link
          href="/search"
          className="rounded-lg bg-indigo-600 px-8 py-3 font-semibold text-white hover:bg-indigo-500 transition-colors inline-block"
        >
          Go to Job Search
        </Link>
      </div>
    </div>
  );
}
