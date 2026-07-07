"""US/Canada company career pages."""

US_CANADA_JOB_SOURCES = [
    {"name": "Pickle Robot", "url": "https://jobs.lever.co/picklerobot", "region": "US/Canada", "type": "company", "ats": "lever", "ats_slug": "picklerobot"},
    {"name": "Prime Intellect", "url": "https://jobs.ashbyhq.com/PrimeIntellect", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "PrimeIntellect"},
    {"name": "Verneek", "url": "https://apply.workable.com/verneek", "region": "US/Canada", "type": "company", "ats": "workable"},

    {"name": "Latitude AI", "url": "https://lat.ai/careers#open-roles", "region": "US/Canada", "type": "company", "playwright": True},
    {"name": "RapDev", "url": "https://www.rapdev.io/company/careers#positions", "region": "US/Canada", "type": "company", "playwright": True},
    {"name": "ULINE", "url": "https://www.uline.jobs/JobSearchResults?culture=en", "region": "US/Canada", "type": "company", "playwright": True},
    {"name": "Via", "url": "https://ridewithvia.com/careers/jobs", "region": "US/Canada", "type": "company", "playwright": True},

    # AI Labs & LLM providers (from career-ops)
    {"name": "Anthropic", "url": "https://job-boards.greenhouse.io/anthropic", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "anthropic"},
    {"name": "Cohere", "url": "https://jobs.ashbyhq.com/cohere", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "cohere"},
    {"name": "Perplexity", "url": "https://jobs.ashbyhq.com/perplexity", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "perplexity"},
    {"name": "CoreWeave", "url": "https://job-boards.greenhouse.io/coreweave", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "coreweave"},

    # Voice AI & Conversational AI
    {"name": "Hume AI", "url": "https://job-boards.greenhouse.io/humeai", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "humeai"},
    {"name": "Sierra", "url": "https://jobs.ashbyhq.com/sierra", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "sierra"},
    {"name": "Decagon", "url": "https://jobs.ashbyhq.com/decagon", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "decagon"},
    {"name": "Ada", "url": "https://job-boards.greenhouse.io/ada", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "ada"},

    # AI-native platforms (FDE/SA teams)
    {"name": "Airtable", "url": "https://job-boards.greenhouse.io/airtable", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "airtable"},
    {"name": "Vercel", "url": "https://job-boards.greenhouse.io/vercel", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "vercel"},
    {"name": "Temporal", "url": "https://job-boards.greenhouse.io/temporal", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "temporal"},
    {"name": "Glean", "url": "https://job-boards.greenhouse.io/gleanwork", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "gleanwork"},
    {"name": "Clay Labs", "url": "https://jobs.ashbyhq.com/claylabs", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "claylabs"},
    {"name": "LangChain", "url": "https://jobs.ashbyhq.com/langchain", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "langchain"},

    # AI infra & LLMOps
    {"name": "Arize AI", "url": "https://job-boards.greenhouse.io/arizeai", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "arizeai"},
    {"name": "Pinecone", "url": "https://jobs.ashbyhq.com/pinecone", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "pinecone"},
    {"name": "RunPod", "url": "https://job-boards.greenhouse.io/runpod", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "runpod"},
    {"name": "Supabase", "url": "https://jobs.ashbyhq.com/supabase", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "supabase"},
    {"name": "Zep AI", "url": "https://www.getzep.com/careers", "region": "US/Canada", "type": "company", "playwright": True},

    # Dev tools & AI infra
    {"name": "Resend", "url": "https://jobs.ashbyhq.com/resend", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "resend"},
    {"name": "Clerk", "url": "https://jobs.ashbyhq.com/clerk", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "clerk"},
    {"name": "Inngest", "url": "https://jobs.ashbyhq.com/inngest", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "inngest"},
    {"name": "WorkOS", "url": "https://jobs.ashbyhq.com/workos", "region": "US/Canada", "type": "company", "ats": "ashby", "ats_slug": "workos"},
    {"name": "Hightouch", "url": "https://job-boards.greenhouse.io/hightouch", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "hightouch"},
    {"name": "PlanetScale", "url": "https://job-boards.greenhouse.io/planetscale", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "planetscale"},

    # Generative AI / creative tooling
    {"name": "Runway", "url": "https://job-boards.greenhouse.io/runwayml", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "runwayml"},

    # Canada tech
    {"name": "Safari AI", "url": "https://job-boards.greenhouse.io/safariai", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "safariai"},
    {"name": "Later", "url": "https://job-boards.greenhouse.io/later", "region": "US/Canada", "type": "company", "ats": "greenhouse", "ats_slug": "later"},
]
