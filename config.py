from scraper import OpenRoboticsScraper, WorkdayJobScraper, GreenhouseScraper

def get_scrapers():
    """Returns all active scraper targets."""
    return [
        OpenRoboticsScraper(),
        WorkdayJobScraper(
            company_name="rosennxt",
            wd_host="rosennxt.wd103.myworkdayjobs.com",
            site_id="rosenxt"
        ),
        GreenhouseScraper(
            board_token="arxroboticsgmbh",
            company_name="ARX Robotics"
        )
    ]