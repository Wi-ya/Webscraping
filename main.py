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
    try:
        scrape_carpages_ca(driver)
    finally:
        driver.quit()

def scrape_carpages_ca(driver):
    # Open webpage and wait to load
    driver.get("https://www.carpages.ca")
    driver.implicitly_wait(5)

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
            # Explicitly print before the blocking call
            print(" >> Requesting page...", end=" ", flush=True)
            driver.get(category_url)
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
            page_car_listing_container = (driver.find_element(By.CSS_SELECTOR,
                                        "div[class*='tw:laptop:col-span-8']"))
            car_listings = page_car_listing_container.find_elements(By.CSS_SELECTOR,
                            "div[class='tw:flex tw:gap-6 tw:items-start tw:p-6']")
            for car_listing in car_listings:
                listing_header = car_listing.find_element(By.TAG_NAME, "h4").text
                year = listing_header.split(" ")[0]
                make = listing_header.split(" ")[1]
                model = listing_header.split(" ")[2]
                price = car_listing.find_element(By.CSS_SELECTOR,
                        "span[class*='tw:font-bold tw:text-xl']").text


                mileage_header_box = car_listing.find_element(By.CSS_SELECTOR,
                            "div[class*='tw:col-span-full tw:mobile-lg:col-span-6 tw:laptop:col-span-4']")
                mileage_box = mileage_header_box.find_element(By.CSS_SELECTOR,
                              "div[class*='tw:text-gray-500']")
                car_mileage = mileage_box.text
                if car_mileage != "CALL":
                    car_mileage = ""
                    mileage_number_list = mileage_box.find_elements(By.CLASS_NAME, "number")
                    for mileage_number in mileage_number_list:
                        car_mileage += mileage_number.text
                    car_mileage = car_mileage.replace(",", "")
                    car_mileage = int(car_mileage)
                else:
                    car_mileage = 0



                color = car_listing.find_element(By.CSS_SELECTOR,
                        "span[class*='tw:text-sm tw:font-bold']").text
                print(year, make, model, price, car_mileage, color)
        except NoSuchElementException:
            print("List not found")
        break

    driver.implicitly_wait(10)


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
    chrome_options.page_load_strategy = 'eager'
    # Return options
    return chrome_options

def bypass_captcha(driver):

    # Titles to check for CAPTCHA or waiting pages
    suspicious_titles = ["Just a moment", "Security Check", "Access denied", "Attention Required"]
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

def extract_data_from_listing(car_listing):
    listing_header = car_listing.find_element(By.TAG_NAME, "h4").text
    year = listing_header.split(" ")[0]
    make = listing_header.split(" ")[1]
    model = listing_header.split(" ")[2]
    price = car_listing.find_element(By.CSS_SELECTOR,
                                     "span[class*='tw:font-bold tw:text-xl']").text

    mileage_header_box = car_listing.find_element(By.CSS_SELECTOR,
                                                  "div[class*='tw:col-span-full tw:mobile-lg:col-span-6 tw:laptop:col-span-4']")
    mileage_box = mileage_header_box.find_element(By.CSS_SELECTOR,
                                                  "div[class*='tw:text-gray-500']")
    car_mileage = mileage_box.text
    if car_mileage != "CALL":
        car_mileage = ""
        mileage_number_list = mileage_box.find_elements(By.CLASS_NAME, "number")
        for mileage_number in mileage_number_list:
            car_mileage += mileage_number.text
        car_mileage = car_mileage.replace(",", "")
        car_mileage = int(car_mileage)
    else:
        car_mileage = 0

    color = car_listing.find_element(By.CSS_SELECTOR,
                                     "span[class*='tw:text-sm tw:font-bold']").text
    print(year, make, model, price, car_mileage, color)

if __name__ == "__main__":
    main()