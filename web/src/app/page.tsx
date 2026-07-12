import Link from "next/link";

const FEATURES = [
  {
    title: "AI Job Matching",
    desc: "Upload your resume and get scored job matches (0-100) based on skills, experience, and seniority.",
    icon: "🎯",
  },
  {
    title: "ATS Direct Connect",
    desc: "Scrapes 250+ company career pages (Lever, Greenhouse, Ashby, Workable) — no middlemen.",
    icon: "🔗",
  },
  {
    title: "Application Tracker",
    desc: "Track applied, rejected, and offer statuses. Never re-apply to the same company.",
    icon: "📊",
  },
  {
    title: "Email Alerts",
    desc: "Get daily or weekly digests of new matches delivered to your inbox.",
    icon: "📧",
  },
  {
    title: "Smart Scoring",
    desc: "Considers visa requirements, salary ranges, seniority fit, and skill alignment.",
    icon: "⚡",
  },
  {
    title: "Privacy First",
    desc: "Your resume stays on our servers. No data sold. No tracking across the web.",
    icon: "🔒",
  },
];

const STATS = [
  { value: "250+", label: "Company ATS" },
  { value: "15+", label: "Job Boards" },
  { value: "0-100", label: "Match Score" },
  { value: "100%", label: "Free to Start" },
];

export default function LandingPage() {
  return (
    <div className="relative">
      {/* Hero */}
      <section className="relative overflow-hidden pt-20 pb-32">
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-indigo-600/20 blur-3xl" />
        </div>
        <div className="mx-auto max-w-4xl px-4 text-center">
          <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight">
            Find your next
            <br />
            <span className="text-indigo-400">tech role</span> — fast
          </h1>
          <p className="mt-6 text-lg text-gray-400 max-w-2xl mx-auto">
            AI-powered job search engine for software engineers and IT professionals.
            Upload your resume, get matched to roles scoring 80+, and track every application.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <Link
              href="/search"
              className="rounded-xl bg-indigo-600 px-8 py-3.5 text-lg font-semibold text-white hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-600/25"
            >
              Start Searching
            </Link>
            <a
              href="#features"
              className="rounded-xl border border-gray-700 px-8 py-3.5 text-lg font-semibold text-gray-300 hover:bg-gray-800 transition-colors"
            >
              Learn More
            </a>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-gray-800 bg-gray-900/50">
        <div className="mx-auto max-w-5xl px-4 py-12 grid grid-cols-2 sm:grid-cols-4 gap-8">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-3xl font-bold text-indigo-400">{s.value}</div>
              <div className="mt-1 text-sm text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-3xl font-bold text-center mb-16">
            Everything you need to land your next role
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-gray-800 bg-gray-900/50 p-6 hover:border-indigo-600/50 transition-colors"
              >
                <div className="text-3xl mb-4">{f.icon}</div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 border-t border-gray-800">
        <div className="mx-auto max-w-4xl px-4">
          <h2 className="text-3xl font-bold text-center mb-16">How it works</h2>
          <div className="space-y-12">
            {[
              {
                step: "1",
                title: "Upload your resume",
                desc: "PDF resume parsed automatically — extracts skills, experience, and seniority level.",
              },
              {
                step: "2",
                title: "We search 250+ sources",
                desc: "Company ATS APIs (Lever, Greenhouse, Ashby), job boards (LinkedIn, Indeed, Glassdoor), and Playwright-powered career pages.",
              },
              {
                step: "3",
                title: "Get scored matches",
                desc: "Each job scored 0-100 against your profile. Only roles scoring 65+ are shown. Salary, visa, and relocation info included.",
              },
              {
                step: "4",
                title: "Track & apply",
                desc: "Mark jobs as applied, rejected, or offer. Never re-apply. Get email alerts for new matches.",
              },
            ].map((s) => (
              <div key={s.step} className="flex gap-6 items-start">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-indigo-600 flex items-center justify-center text-lg font-bold">
                  {s.step}
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-1">{s.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 border-t border-gray-800">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to find your next role?</h2>
          <p className="text-gray-400 mb-8">
            Free to start. No credit card required.
          </p>
          <Link
            href="/search"
            className="rounded-xl bg-indigo-600 px-8 py-3.5 text-lg font-semibold text-white hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-600/25"
          >
            Get Started — It&apos;s Free
          </Link>
        </div>
      </section>
    </div>
  );
}
