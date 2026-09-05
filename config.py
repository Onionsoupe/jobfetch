from scraper import OpenRoboticsScraper, WorkdayJobScraper

def get_scrapers():
    """Returns all active scraper targets."""
    return [
        OpenRoboticsScraper(),
        WorkdayJobScraper(
            company_name="rosennxt",
            wd_host="rosennxt.wd103.myworkdayjobs.com",
            site_id="rosenxt"
        )
    ]