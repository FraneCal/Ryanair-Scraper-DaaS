from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import csv
import os
import logging


# ===== CONFIG =====
START_DATE = datetime.strptime("22-09-2025", "%d-%m-%Y")  # countdown start
ORIGIN = "LON"
DESTINATION = "BCN"
STAY_DAYS = 3
ADULTS = 2
# ==================


def setup_logger():
    """Configure logging to file inside logs/ folder."""
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/{datetime.today().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        filename=log_filename,
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    return logging.getLogger()


def build_ryanair_url(date_out: datetime, stay_days=3, origin="LON", destination="BCN", adults=2):
    """Build a Ryanair URL for given departure date and return after stay_days."""
    date_out_str = date_out.strftime("%Y-%m-%d")
    date_in_str = (date_out + timedelta(days=stay_days)).strftime("%Y-%m-%d")

    base_url = "https://www.ryanair.com/ie/en/trip/flights/select"
    params = (
        f"?adults={adults}"
        f"&teens=0&children=0&infants=0"
        f"&dateOut={date_out_str}&dateIn={date_in_str}"
        f"&isConnectedFlight=false&discount=0&promoCode="
        f"&isReturn=true"
        f"&originMac={origin}&destinationIata={destination}"
        f"&tpAdults={adults}&tpTeens=0&tpChildren=0&tpInfants=0"
        f"&tpStartDate={date_out_str}&tpEndDate={date_in_str}"
        f"&tpDiscount=0&tpPromoCode="
        f"&tpOriginMac={origin}&tpDestinationIata={destination}"
    )

    return base_url + params, date_out_str, date_in_str


def scrape_prices(driver, url):
    """Open Ryanair page and scrape departure/return prices.
    If no price is available, return 'N/A'."""
    driver.get(url)

    # Accept cookies if popup appears
    try:
        accept_cookies = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="cookie-popup-with-overlay"]/div/div[3]/button[3]'))
        )
        accept_cookies.click()
    except TimeoutException:
        pass

    # Wait for prices to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.date-item__price--selected"))
        )
    except TimeoutException:
        return "N/A", "N/A"

    time.sleep(2)

    prices_divs = driver.find_elements(By.CSS_SELECTOR, "div.date-item__price--selected")

    dep_price, ret_price = "N/A", "N/A"

    if len(prices_divs) >= 1:
        try:
            dep_integers = prices_divs[0].find_element(By.CSS_SELECTOR, "span.price__integers").text.strip()
            dep_decimals = prices_divs[0].find_element(By.CSS_SELECTOR, "span.price__decimals").text.strip()
            dep_price = f"{dep_integers}.{dep_decimals}"
        except Exception:
            dep_price = "N/A"

    if len(prices_divs) >= 2:
        try:
            ret_integers = prices_divs[1].find_element(By.CSS_SELECTOR, "span.price__integers").text.strip()
            ret_decimals = prices_divs[1].find_element(By.CSS_SELECTOR, "span.price__decimals").text.strip()
            ret_price = f"{ret_integers}.{ret_decimals}"
        except Exception:
            ret_price = "N/A"

    return dep_price, ret_price


if __name__ == "__main__":
    logger = setup_logger()
    logger.info("🚀 Scraper started.")

    # Setup Selenium Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # ideal for cron job
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # CSV file
    filename = "ryanair_LON_BCN.csv"
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header only if file is new
        if not file_exists:
            writer.writerow([
                "scrape_date",
                "days_before_departure",
                "date_out",
                "date_in",
                "departure_price",
                "return_price"
            ])

        today = datetime.today()
        scrape_date = today.strftime("%Y-%m-%d")

        # How many days left to scrape? (30 down to 0)
        days_passed = (today.date() - START_DATE.date()).days
        days_left = max(30 - days_passed, 0)

        logger.info(f"Scraping window: {days_left} days ahead")

        for i in range(days_left, -1, -1):
            dep_date = today + timedelta(days=i)
            url, date_out, date_in = build_ryanair_url(dep_date, stay_days=STAY_DAYS,
                                                       origin=ORIGIN, destination=DESTINATION, adults=ADULTS)

            dep_price, ret_price = scrape_prices(driver, url)

            days_before_departure = (dep_date - today).days
            writer.writerow([scrape_date, days_before_departure, date_out, date_in, dep_price, ret_price])

            logger.info(f"{scrape_date} | {days_before_departure}d before | Out:{dep_price} | In:{ret_price}")

    driver.quit()
    logger.info("✅ Scraper finished successfully.")
