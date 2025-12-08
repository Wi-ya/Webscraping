import random
import time

import setuptools
from time import sleep

from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import none_of
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import undetected_chromedriver as uc

def main():
    # Access Chrome webdriver with selected preferences to block requests
    driver = uc.Chrome(options=no_location_options(), version_main=142)

    # Throw error if loading takes longer than 30
    driver.set_page_load_timeout(15)
    driver.implicitly_wait(5);
    try:
        scrape_carpages_ca(driver)

    finally:
        driver.quit()

def scrape_carpages_ca(driver):
    # Open webpage and wait to load
    driver.get("https://www.carpages.ca")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Handle cookie requests before scraping
    cookie_handler(driver)

    # Get URL links for each category
    category_container = driver.find_element(By.CSS_SELECTOR, "div.category-jellybeans")
    categories = category_container.find_elements(By.TAG_NAME, "a")
    raw_urls = [c.get_attribute("href") for c in categories if c.get_attribute("href")]

    # Remove duplicates
    category_urls = list(dict.fromkeys(raw_urls))

    # Access each category webpage
    for category_url in category_urls:
        try:
            navigate_page.count = 0
            # Explicitly print before the blocking call
            print(" >> Requesting page...", end=" ", flush=True)
            driver.get(category_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("Done.", flush=True)

            bypass_captcha(driver)
            navigate_category(driver)
            sleep(random.uniform(5,10))

        except TimeoutException:
            # Keep browser open to keep looping
            print("Page load timed out! Forcing stop to continue scraping.")
            driver.execute_script("window.stop();")
            bypass_captcha(driver)
            navigate_category(driver)  # Try to scrape whatever loaded

        except Exception as e:
            print(f"Skip {category_url} because of error: {e}")
            continue  # Go to the next category

def navigate_category(driver):
    print(f"Navigating in {driver.title}")

    while True:
        try:
            header_text = driver.find_element(By.TAG_NAME, "h1").text
            # Extract body_type which is the same for all cars in one category
            if "New and Used" in header_text:
                body_type = header_text.replace("New and Used ", "").replace(" for Sale", "")
            else:
                body_type = header_text
            # Set body_type of all entries in one category to be the same
            # Only changes when moving to new category
            if body_type == "Cars":
                body_type = "hybrid"
            elif "Hatchbacks" in body_type:
                body_type = "Hatchback"
            elif "SUV" in body_type:
                body_type = "SUV"
            elif "Minivan" in body_type:
                body_type = "Minivan"
            else:
                body_type = body_type[:-1]
            navigate_page(driver,body_type)

            # After navigating page try to move to next page in the same category
            next_link = driver.find_elements(By.LINK_TEXT,"→")
            proceed_to_next = False

            if next_link:
                next_btn = next_link[0]

                # Check if button is disabled or if there is no link
                btn_class = next_btn.get_attribute("class") or ""

                # If the button is not disabled go ahead and go to next page
                if "disabled" not in btn_class and next_btn.is_enabled():
                    proceed_to_next = True

            if proceed_to_next:
                # Track current page count of cars (1-50 or 51-100)
                curr_page_numbers = driver.find_element(By.CSS_SELECTOR,
                                    "span[class*='tw:font-bold']").text

                next_link[0].click()

                # Wait for the loading to new page and for old page to go stale
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "span[class*='tw:font-bold']").text\
                                  != curr_page_numbers
                    )
                    print(" >> Page loaded successfully.")
                except Exception as e:
                    print(" >> Timed out waiting for new page to load.")

            else:
                print("No link found. Must be last page of category.")
                break

        except Exception as e:
            print(f"Skip page because of error: {e}")
            break

def navigate_page(driver, body_type):
    if not hasattr(navigate_page, "count"):
        navigate_page.count = 0
    navigate_page.count += 1
    print(f"Navigating page {navigate_page.count} in {driver.title}")
    try:
        # Wait for container to appear to access
        page_car_listing_container = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='tw:laptop:col-span-8']")))
        # Get list of all car_listings to scrape data
        car_listings = page_car_listing_container.find_elements(By.CSS_SELECTOR,
                "div[class*='tw:flex'][class*='tw:p-6']")
        if not car_listings:
            print("No car listing found.")
        else:
            for car_listing in car_listings:
                extract_data_from_listing(car_listing, body_type)
    except (NoSuchElementException, TimeoutException):
        print("(Page content timed out or empty)")

def cookie_handler(driver):
    try:
        print("Checking for cookie banner...")
        # Wait for popup to press the button consent
        # Press consent to go pass the cookie popup
        cookie_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Consent')] | //div[contains(text(), 'Consent') \
                and @role='button']"))
        )

        cookie_btn.click()
        print("Cookie banner dismissed.")
        sleep(2)  # Time for popup to disappear

    except Exception as e:
        print(f"Cookie banner skipped or not found. Details: {e}")

def no_location_options():
    chrome_options = Options()
    # Define the preferences for browser to block location request and notifications
    prefs = {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.notifications": 2
    }

    # Add preferences to options
    chrome_options.add_experimental_option("prefs", prefs)
    # Change so page does not wait for ads/pictures
    chrome_options.page_load_strategy = 'none'
    # Return options
    return chrome_options

def bypass_captcha(driver):

    # Titles to check for CAPTCHA or waiting pages
    suspicious_titles = ["Just a moment", "Security Check", "Access denied", "Attention Required",
                         "Checking your browser", "reCAPTCHA", "Cloudflare"]
    accurate_titles = ["New and Used", "Carpages.ca"]

    max_wait = 20  # Wait time to ensure that manual captcha entry is required
    start_time = time.time()

    while True:
        # Check current page title
        current_title = driver.title
        different_page = any(t in current_title for t in suspicious_titles)\
                         or not any(t in current_title for t in accurate_titles)

        # If real page is loaded then can exit this function
        if not different_page:
            return

        # If still waiting on different page, check time elapsed
        elapsed = time.time() - start_time

        if elapsed > max_wait:
            # If waiting too long then there must be CAPTCHA to solve, solve manually
            print("\n" + "!" * 50)
            print(f"!!! STUCK ON: {current_title} !!!")
            print("Auto-redirect failed. Please solve manually in browser.")
            print("!" * 50 + "\n")

            # After solving enter anything to exit this function and continue scraping
            input("Press Enter to resume script...")
            return

        # Wait and check again
        print(f" >> Time waiting: ({int(elapsed)}s)")
        time.sleep(2)

def extract_data_from_listing(car_listing, body_type):
    # Extract year, make, model, link and price
    listing_header = car_listing.find_element(By.TAG_NAME, "h4").text
    year = listing_header.split(" ")[0]
    make = listing_header.split(" ")[1]
    model = listing_header.split(" ")[2]
    href_link = car_listing.find_element(By.TAG_NAME, "a").get_attribute("href")
    price = car_listing.find_element(By.CSS_SELECTOR,
                                     "span[class*='tw:font-bold tw:text-xl']").text

    # Extract mileage, check if mileage exists
    mileage_header_box = car_listing.find_element(By.CSS_SELECTOR,
                        "div[class*='tw:col-span-full tw:mobile-lg:col-span-6 tw:laptop:col-span-4']")
    mileage_box = mileage_header_box.find_element(By.CSS_SELECTOR,
                                                  "div[class*='tw:text-gray-500']")
    raw_mileage = mileage_box.text
    car_mileage = 0

    if "CALL" not in raw_mileage and raw_mileage.strip() != "":
        # Extract only digits
        mileage_number_list = mileage_box.find_elements(By.CLASS_NAME, "number")
        temp_mileage = ""
        for num in mileage_number_list:
            temp_mileage += num.text

        clean_mileage = temp_mileage.replace(",", "").strip()
        if clean_mileage.isdigit():
            car_mileage = int(clean_mileage)

    color = car_listing.find_element(By.CSS_SELECTOR,
                                     "span[class*='tw:text-sm tw:font-bold']").text
    print(year, make, model, price, car_mileage, color, href_link, body_type)

if __name__ == "__main__":
    main()