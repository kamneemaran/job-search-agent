"""APAC company career pages."""

APAC_JOB_SOURCES = [
    {"name": "SmartNews via Recruiter", "url": "https://apply.workable.com/smartnews", "region": "APAC", "type": "company", "ats": "workable"},

    {"name": "ABB Singapore via Recruiter", "url": "https://careers.abb/global/en/search-results", "region": "APAC", "type": "company", "playwright": True},
    {"name": "ST Engineering", "url": "https://www.stengg.com/en/careers/global-talent-programme", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Unisoft", "url": "https://unisoft.sg", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Grab", "url": "https://www.grab.careers/en/jobs", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Skill Quotient Group", "url": "https://skillquotientgroup.com/career", "region": "APAC", "type": "company", "playwright": True},
    {"name": "NCS Group", "url": "https://www.ncs.co/careers", "region": "APAC", "type": "company", "playwright": True},
    {"name": "E Financial Careers", "url": "https://www.efinancialcareers.sg", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Mujin", "url": "https://mujin-corp.com/company/careers", "region": "APAC", "type": "company", "playwright": True},
    {"name": "PayPay", "url": "https://about.paypay.ne.jp/career/en/job-category/product-development/#sec-02", "region": "APAC", "type": "company", "playwright": True},
    {"name": "PayPay via Recruiter", "url": "https://about.paypay.ne.jp/career/en", "region": "APAC", "type": "company", "playwright": True},
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

    # Indian SAP consultancies / system integrators
    {"name": "HCL Technologies", "url": "https://careers.hcltech.com/go/NonTPDemand/9558355/", "region": "India", "type": "company", "playwright": True},
    {"name": "Tech Mahindra", "url": "https://careers.techmahindra.com/currentopportunity.aspx", "region": "India", "type": "company", "playwright": True},
    {"name": "LTIMindtree", "url": "https://www.ltimindtree.com/careers/", "region": "India", "type": "company", "playwright": True},
    {"name": "Mphasis", "url": "https://www.mphasis.com/careers.html", "region": "India", "type": "company", "playwright": True},
    {"name": "Hexaware", "url": "https://jobs.hexaware.com/#en/sites/CX_1/jobs", "region": "India", "type": "company", "playwright": True},
    {"name": "Birlasoft", "url": "https://jobs.birlasoft.com/search/?createNewAlert=false&q=&optionsFacetsDD_country=&optionsFacetsDD_department=", "region": "India", "type": "company", "playwright": True},
    {"name": "Zensar (EU)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435067%3B300000000435373%3B100000025362613%3B100000025362627%3B100000025364817", "region": "EU", "type": "company", "playwright": True},
    {"name": "Zensar (India)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435151%3B300000000389881%3B300000000435178%3B300000000435310%3B300000000435430", "region": "India", "type": "company", "playwright": True},
    {"name": "Zensar (US)", "url": "https://fa-etvl-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000435529%3B100000010729607%3B100000010729641%3B100000010729647%3B100000010729654%3B100000010783527", "region": "US", "type": "company", "playwright": True},

    # APAC tech companies
    {"name": "Tencent", "url": "https://careers.tencent.com/en-us/search.html?query=ot_40001002,ot_40001001,ot_40001003,ot_40001004,ot_40001005,ot_40001006,at_1", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Sea Limited", "url": "https://career.sea.com/jobs?&keyword=&job_categories=6&teams=107458", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Alibaba (AIDC)", "url": "https://aidc-jobs.alibaba.com/home?lang=en", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Rakuten", "url": "https://japan-job-en.rakuten.careers/engineering-en", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Samsung", "url": "https://www.samsungcareers.com/?lang=en", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Wipro", "url": "https://careers.wipro.com/go/Engineering/9369255/", "region": "APAC", "type": "company", "playwright": True},
    {"name": "Flipkart", "url": "https://www.flipkartcareers.com/jobslist", "region": "India", "type": "company", "playwright": True},
]
