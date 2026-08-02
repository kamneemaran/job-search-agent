"""APAC company career pages."""

APAC_JOB_SOURCES = [
    {"name": "SmartNews via Recruiter", "url": "https://apply.workable.com/smartnews", "region": "APAC", "type": "company", "ats": "workable"},

    {"name": "ABB Singapore via Recruiter", "url": "https://careers.abb/global/en/search-results", "region": "APAC", "type": "company", "playwright": True},
    {"name": "ST Engineering", "url": "https://www.stengg.com/en/careers/global-talent-programme", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Unisoft", "url": "https://unisoft.sg", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Grab", "url": "https://www.grab.careers/en/jobs", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Skill Quotient Group", "url": "https://skillquotientgroup.com/career", "region": "APAC", "type": "company", "playwright": True},
    {"name": "NCS Group", "url": "https://www.ncs.co/careers?function=Information%20Technology", "region": "APAC", "type": "company", "playwright": True},
    {"name": "E Financial Careers", "url": "https://www.efinancialcareers.sg", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Mujin", "url": "https://mujin-corp.com/careers#full-time-opportunities", "region": "APAC", "type": "company", "playwright": True},
    {"name": "PayPay (Product)", "url": "https://about.paypay.ne.jp/career/en/job-category/product-development/", "region": "APAC", "type": "company", "playwright": True},
    {"name": "PayPay (Corporate)", "url": "https://about.paypay.ne.jp/career/en/job-category/corporate/", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Sciente International", "url": "https://www.scienteinternational.com/candidates/it-technology-jobs", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Aryan Solutions", "url": "https://aryan-solutions.com/permanent-recruitment", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Workforce Australia via Recruiter", "url": "https://www.workforceaustralia.gov.au/individuals/jobs/details/2338683139#contentA", "region": "APAC", "type": "company", "playwright": True},

    # Indian product companies
    {"name": "Swiggy", "url": "https://careers.swiggy.com/#!/jobs", "region": "India", "type": "company", "playwright": True},
    {"name": "Razorpay", "url": "https://job-boards.greenhouse.io/razorpaysoftwareprivatelimited", "region": "India", "type": "company", "ats": "greenhouse", "ats_slug": "razorpaysoftwareprivatelimited"},
    {"name": "CRED", "url": "https://jobs.lever.co/cred", "region": "India", "type": "company", "ats": "lever", "ats_slug": "cred"},
    {"name": "Nykaa", "url": "https://careers.nykaa.com/", "region": "India", "type": "company", "playwright": True},
    {"name": "MakeMyTrip", "url": "https://careers.makemytrip.com/", "region": "India", "type": "company", "playwright": True, "timeout": 30000},
    {"name": "OYO", "url": "https://www.oyorooms.com/careers/", "region": "India", "type": "company", "playwright": True},
    {"name": "Zerodha", "url": "https://zerodha.com/careers", "region": "India", "type": "company", "playwright": True},
    {"name": "Groww", "url": "https://job-boards.greenhouse.io/groww", "region": "India", "type": "company", "ats": "greenhouse", "ats_slug": "groww"},
    {"name": "Pine Labs", "url": "https://www.pinelabs.com/careers/open-jobs", "region": "India", "type": "company", "playwright": True},
    {"name": "InMobi", "url": "https://www.inmobi.com/company/careers", "region": "India", "type": "company", "playwright": True},
    {"name": "Urban Company", "url": "https://careers.urbancompany.com/", "region": "India", "type": "company", "playwright": True},
    {"name": "Meesho", "url": "https://jobs.lever.co/meesho", "region": "India", "type": "company", "ats": "lever", "ats_slug": "meesho"},

    # Indian recruitment agencies
    {"name": "Careernet", "url": "https://mycareernet.co/mycareernet/jobs", "region": "India", "type": "company", "playwright": True},
    {"name": "Persol India", "url": "https://jobs.persolindia.com/?utm_source=internal_navigation&utm_medium=persolindia_site&utm_campaign=country_site_to_job_portal&utm_content=hero_search_jobs&industry=Information%2520Technology,Admin%252FMaintenance%252FSecurity%252FDatawarehousing,Programming%2520%2526%2520Design,Project%2520Management,QA%252FTesting%252FDocumentation,Senior%2520Management,System%2520Design%252FImplementation%252FERP%252FCRM&page=1", "region": "India", "type": "company", "playwright": True},
    {"name": "Placement India", "url": "https://www.placementindia.com/job-search/search.php?filter=relevance&id2=refine_search&seeker_search_keyword=enter+skills%2C+designation%2C+etc&job_by_functional_area_refine%5B%5D=100004&job_by_functional_area_refine%5B%5D=103268&job_by_functional_area_refine%5B%5D=103272&job_by_functional_area_refine%5B%5D=103279&job_by_functional_area_refine%5B%5D=103280&job_by_functional_area_refine%5B%5D=100002&job_by_functional_area_refine%5B%5D=103285&job_by_functional_area_refine%5B%5D=103270&job_by_functional_area_refine%5B%5D=103275&job_by_functional_area_refine%5B%5D=103278&job_by_functional_area_refine%5B%5D=103283", "region": "India", "type": "company", "playwright": True},

    # Indian SAP consultancies / system integrators
    {"name": "HCL Technologies", "url": "https://careers.hcltech.com/go/NonTPDemand/9558355/", "region": "India", "type": "company", "playwright": True},
    {"name": "Tech Mahindra", "url": "https://careers.techmahindra.com/CurrentOpportunity.aspx#Advance", "region": "India", "type": "company", "playwright": True},
    {"name": "LTIMindtree", "url": "https://careers.ltimindtree.com/search/?q=&sortColumn=referencedate&sortDirection=desc", "region": "India", "type": "company", "playwright": True},
    {"name": "Mphasis", "url": "https://mphasis.ripplehire.com/candidate/?token=ty4DfyWddnOrtpclQeia&source=CAREERSITE#list", "region": "India", "type": "company", "playwright": True},
    {"name": "Hexaware", "url": "https://jobs.hexaware.com/#en/sites/CX_1/jobs", "region": "India", "type": "company", "playwright": True},
    {"name": "Birlasoft", "url": "https://jobs.birlasoft.com/search/?createNewAlert=false&q=&optionsFacetsDD_country=&optionsFacetsDD_department=", "region": "India", "type": "company", "playwright": True},
    {"name": "Zensar (EU)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435067%3B300000000435373%3B100000025362613%3B100000025362627%3B100000025364817", "region": "EU", "type": "company", "playwright": True},
    {"name": "Zensar (India)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435151%3B300000000389881%3B300000000435178%3B300000000435310%3B300000000435430", "region": "India", "type": "company", "playwright": True},
    {"name": "Zensar (US)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435529%3B100000010729607%3B100000010729641%3B100000010729647%3B100000010729654%3B100000010783527", "region": "US", "type": "company", "playwright": True},

    # APAC tech companies
    {"name": "Tencent", "url": "https://careers.tencent.com/en-us/search.html?query=ot_40001002,ot_40001001,ot_40001003,ot_40001004,ot_40001005,ot_40001006,at_1", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Sea Limited", "url": "https://career.sea.com/jobs?job_categories=6", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Alibaba (AIDC)", "url": "https://aidc-jobs.alibaba.com/en/off-campus/position-list?lang=en", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Rakuten", "url": "https://japan-job-en.rakuten.careers/search-jobs?orgIds=31271&acm=ALL&alrpm=ALL&ascf=[%7B%22key%22:%22custom_fields.CategoryGroup%22,%22value%22:%22Engineering%22%7D]", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Mercari", "url": "https://careers.mercari.com/jobs/?job_category=jc-engineering+engineering+corporate-engineering+security-engineering", "region": "APAC", "type": "company", "playwright": True},
    {"name": "LINE (Yahoo Japan)", "url": "https://www.lycorp.co.jp/en/recruit/career/job-categories/#all", "region": "APAC", "type": "company", "playwright": True},

    {"name": "NTT Data", "url": "https://www.nttdata.com/global/en/careers", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Panasonic", "url": "https://careers.na.panasonic.com/jobs?categories=Engineering%7CIT&page=1", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Samsung", "url": "https://www.samsungcareers.com/?lang=en", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Wipro", "url": "https://careers.wipro.com/go/Engineering/9369255/", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Flipkart", "url": "https://www.flipkartcareers.com/jobslist", "region": "India", "type": "company", "playwright": True},

    # European / Swiss companies (scanned in EU batch via apac_companies import)
    {"name": "Logitech", "url": "https://jobs.jobvite.com/logitech/", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "ELCA", "url": "https://www.elca.ch/en/careers", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Avaloq", "url": "https://www.avaloq.com/careers/job-openings", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Lonza", "url": "https://www.lonza.com/careers", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "CSL Behring", "url": "https://www.csl.com/careers", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Biogen", "url": "https://biibhr.wd3.myworkdayjobs.com/external?jobFamilyGroup=4104486c9e6610a62b3a0bd68efa03d9&jobFamilyGroup=4104486c9e6610a62b3a444f21ca0405&jobFamilyGroup=4104486c9e6610a62b3a19135a3a03e3&jobFamilyGroup=5ab74f024f490150e212acde4c01760e", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "BDO", "url": "https://www.bdo.global/en-gb/careers", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Bobst", "url": "https://jobs.bobst.com/Jobs/All", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Coca-Cola HBC Switzerland", "url": "https://careers.coca-colahellenic.com/", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Siemens Schweiz", "url": "https://jobs.siemens.com/", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Nestlé", "url": "https://www.nestle.com/jobs", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Barry Callebaut", "url": "https://www.barry-callebaut.com/en/group/careers", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Leica Geosystems", "url": "https://hexagon.com/company/careers/job-listings#jl_companyname=Geosystems&jl_e=0", "region": "Switzerland", "type": "company", "playwright": True},
    {"name": "Rivella Group", "url": "https://rivella-group.com/karriere/offene-stellen/", "region": "Switzerland", "type": "company", "playwright": True},

    # AI companies (from career-ops integration)
    {"name": "Glacis AI", "url": "https://jobs.ashbyhq.com/glacis-ai", "region": "APAC", "type": "company", "ats": "ashby", "ats_slug": "glacis-ai"},
    {"name": "Maxim AI", "url": "https://www.getmaxim.ai/careers", "region": "APAC", "type": "company", "playwright": True},
]
