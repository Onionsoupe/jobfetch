from scraper import (
    OpenRoboticsScraper,
    WorkdayJobScraper,
    GreenhouseScraper,
    SoftgardenScraper,
    AshbyScraper,
    PersonioScraper
)

# Personio targets
PERSONIO_TARGETS = [
    {
        "tenant_slug": "ubica-robotics",
        "company_name": "UBICA Robotics",
        "domain": "jobs.personio.de"
    },
    {
        "tenant_slug": "hive-robotics",
        "company_name": "Hive Robotics",
        "domain": "jobs.personio.com"
    },
    {
        "tenant_slug": "autonomous-teaming",  
        "company_name": "Autonomous Teaming Solutions",
        "domain": "jobs.personio.de"
    },
]

# Greenhouse targets (Supports both standard US and EU domains)
GREENHOUSE_TARGETS = [
    {
        "board_token": "arxroboticsgmbh",
        "company_name": "ARX Robotics"
        # Defaults to domain="boards-api.greenhouse.io"
    },
    {
        "board_token": "agilerobotsse",
        "company_name": "Agile Robots", # Handles EU Greenhouse hosted boards
    },
]


def get_scrapers():
    scrapers = []

    # Existing standalone scrapers
    scrapers.append(OpenRoboticsScraper())
    scrapers.append(WorkdayJobScraper(company_name="rosennxt", wd_host="rosennxt.wd103.myworkdayjobs.com", site_id="rosenxt"))
    scrapers.append(SoftgardenScraper(tenant_domain="neura-mobile-robots", company_name="NEURA Mobile Robots"))
    scrapers.append(AshbyScraper(organization_slug="sensmore"))

    # Config-driven Personio loop
    for target in PERSONIO_TARGETS:
        scrapers.append(PersonioScraper(**target))

    # Config-driven Greenhouse loop
    for target in GREENHOUSE_TARGETS:
        scrapers.append(GreenhouseScraper(**target))

    return scrapers