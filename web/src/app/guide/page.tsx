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
                <li><strong className="text-white">Send Now (On-Demand):</strong> Want an instant update? Click the "Send Now" button. It will trigger an on-demand background scan to compile matching jobs from multiple regions and company career pages. Please note that scanning 250+ company sites is comprehensive and takes time, so you will receive the email as soon as the background scan is complete (which can take several hours).</li>
              </ul>
              <p className="text-gray-500 text-xs mt-2 italic">
                Note: On-demand "Send Now" requests are limited to once every 8 hours to protect your API quotas.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* Section 5 */}
      <section className="rounded-2xl border border-gray-800 bg-gray-900/40 p-8">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xl text-indigo-400 font-bold border border-indigo-500/20">5</span>
          <div className="space-y-2 w-full">
            <h2 className="text-xl font-semibold text-white">Job Sources We Cover</h2>
            <p className="text-gray-400 text-sm leading-relaxed">
              JobPilot aggregates listings from <strong className="text-white">50+ job boards</strong> and <strong className="text-white">1260+ ATS company career pages</strong>. Sources are organized by region and run in parallel batches.
            </p>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              {/* Global / Major Boards */}
              <div className="space-y-1">
                <h3 className="text-indigo-400 font-semibold text-xs uppercase tracking-wider">Global Major Boards</h3>
                <ul className="list-disc pl-5 text-gray-400 space-y-0.5 text-xs">
                  <li>LinkedIn</li>
                  <li>Indeed</li>
                  <li>Glassdoor</li>
                  <li>Naukri</li>
                  <li>SimplyHired</li>
                  <li>Foundit (ex-Monster India)</li>
                  <li>TimesJobs</li>
                  <li>Instahyre</li>
                  <li>WomenInTech</li>
                  <li>Adzuna</li>
                  <li>Reed (UK)</li>
                  <li>Jobsite (UK)</li>
                </ul>
              </div>

              {/* APAC */}
              <div className="space-y-1">
                <h3 className="text-indigo-400 font-semibold text-xs uppercase tracking-wider">APAC</h3>
                <ul className="list-disc pl-5 text-gray-400 space-y-0.5 text-xs">
                  <li>Seek (Australia)</li>
                  <li>Jora (Australia)</li>
                </ul>
              </div>

              {/* Europe */}
              <div className="space-y-1">
                <h3 className="text-indigo-400 font-semibold text-xs uppercase tracking-wider">Europe</h3>
                <ul className="list-disc pl-5 text-gray-400 space-y-0.5 text-xs">
                  <li>Xing (Germany)</li>
                  <li>StepStone (Germany)</li>
                  <li>MonsterDE (Germany)</li>
                  <li>JobsinGermany</li>
                  <li>Bundesagentur (Germany)</li>
                  <li>Freelancermap (Germany)</li>
                  <li>JobsCh (Switzerland)</li>
                  <li>NetEmpregos (Portugal)</li>
                  <li>SAPOEmprego (Portugal)</li>
                  <li>Infoempleo (Spain)</li>
                  <li>IndeedNL (Netherlands)</li>
                  <li>Intermediair (Netherlands)</li>
                  <li>NationaleVacaturebank (Netherlands)</li>
                  <li>IamExpat (Netherlands)</li>
                  <li>WelcomeToNL (Netherlands)</li>
                  <li>TogetherAbroad (Netherlands)</li>
                  <li>WorkInLux (Luxembourg)</li>
                  <li>WorkinFinland (Finland)</li>
                  <li>EURES (EU-wide)</li>
                  <li>EnglishJobSearch (EU)</li>
                  <li>Bulldogjob (Poland/EU)</li>
                </ul>
              </div>

              {/* Remote-First Boards */}
              <div className="space-y-1">
                <h3 className="text-indigo-400 font-semibold text-xs uppercase tracking-wider">Remote-First Boards</h3>
                <ul className="list-disc pl-5 text-gray-400 space-y-0.5 text-xs">
                  <li>WeWorkRemotely</li>
                  <li>Remotive</li>
                  <li>RemoteOK</li>
                  <li>SkipTheDrive</li>
                  <li>WorkingNomads</li>
                  <li>Jobspresso</li>
                  <li>WorkAtAStartup</li>
                  <li>ArcDev</li>
                  <li>Himalayas</li>
                  <li>NoDesk</li>
                  <li>Workew</li>
                  <li>Arbeitnow</li>
                  <li>VisaSponsor</li>
                  <li>Incluso</li>
                  <li>Crossover</li>
                  <li>Kelly</li>
                </ul>
              </div>
            </div>

            {/* Company ATS sources */}
            <div className="mt-4">
              <h3 className="text-indigo-400 font-semibold text-xs uppercase tracking-wider mb-1">ATS Company Career Pages</h3>
              <p className="text-gray-400 text-xs leading-relaxed">
                <strong className="text-white">1260+ companies</strong> across 6 region files — <strong className="text-white">Global</strong>, <strong className="text-white">US/Canada</strong>, <strong className="text-white">EU</strong>, <strong className="text-white">APAC</strong>, <strong className="text-white">Middle East</strong>, and <strong className="text-white">Remote-first</strong>. Each company's ATS (Greenhouse, Lever, Workday, Taleo, etc.) is scraped directly. Plus a Google Sheets links sheet with 50+ additional job board URLs.
              </p>
            </div>
          </div>
        </div>
      </section>

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
