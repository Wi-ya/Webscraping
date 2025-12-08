import csv
import random
import time
from collections import defaultdict

import setuptools
from time import sleep

from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import undetected_chromedriver as uc

def main():
    all_rows = []
    category_rows = defaultdict(list)

    # Access Chrome webdriver with selected preferences to block requests
    driver = uc.Chrome(options=no_location_options(), version_main=142)

    # Throw error if loading takes longer than 30
    driver.set_page_load_timeout(15)
    driver.implicitly_wait(5);
    try:
        scrape_carpages_ca(driver, all_rows, category_rows)
    finally:
        driver.quit()

    if all_rows:
        write_rows_to_csv(all_rows, filepath="all_listings.csv")
        write_category_csvs(category_rows)
        print(f"Saved {len(all_rows)} listings to all_listings.csv and {len(category_rows)} category files.")
    else:
        print("No listings scraped; CSVs not written.")

def scrape_carpages_ca(driver, all_rows, category_rows):
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

    visited_urls = set()

    # Access each category webpage
    for category_url in category_urls:
        if category_url in visited_urls:
            print(f"Skipping already visited category: {category_url}")
            continue
        try:
            navigate_page.count = 0
            # Explicitly print before the blocking call
            print(" >> Requesting page...", end=" ", flush=True)
            driver.get(category_url)
            # Reduced timeout - body should load quickly
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                pass  # Continue anyway, page might still be loading
            print("Done.", flush=True)

            bypass_captcha(driver)
            navigate_category(driver, all_rows, category_rows)
            sleep(random.uniform(2,4))  # Reduced sleep time between categories
            visited_urls.add(category_url)

        except TimeoutException:
            # Keep browser open to keep looping
            print("Page load timed out! Forcing stop to continue scraping.")
            driver.execute_script("window.stop();")
            bypass_captcha(driver)
            navigate_category(driver, all_rows, category_rows)  # Try to scrape whatever loaded
            visited_urls.add(category_url)

        except Exception as e:
            print(f"Skip {category_url} because of error: {e}")
            continue  # Go to the next category

def navigate_category(driver, all_rows, category_rows):
    print(f"Navigating in {driver.title}")
    # Reset page counter for each new category
    navigate_page.count = 0
    
    # Wait for page to be fully loaded after any redirects/captcha
    bypass_captcha(driver)
    
    # Wait for the actual page content to be ready (shorter timeout, continue if fails)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
    except TimeoutException:
        print(" >> Warning: Page header not found, trying to continue...")
    
    # Get body_type once at the start
    try:
        header_text = driver.find_element(By.TAG_NAME, "h1").text
        if "New and Used" in header_text:
            body_type = header_text.replace("New and Used ", "").replace(" for Sale", "")
        else:
            body_type = header_text
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
    except Exception as e:
        print(f" >> Error extracting body_type: {e}")
        return  # Can't proceed without body_type
    
    # Scrape the first page - wait for it to be ready
    last_container = navigate_page(driver, body_type, all_rows, category_rows)
    if last_container is None:
        print(" >> Failed to load first page, skipping category.")
        return
    
    last_url = driver.current_url

    while True:
        try:
            # Quick captcha check (non-blocking if page is already loaded)
            try:
                bypass_captcha(driver)
            except Exception:
                pass  # Continue if captcha check fails
            
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
                prev_url = driver.current_url
                # Get current page indicator text if available (e.g., "1-50" or "51-100")
                try:
                    page_indicator = driver.find_element(By.CSS_SELECTOR, "span[class*='tw:font-bold']")
                    prev_page_text = page_indicator.text
                except Exception:
                    prev_page_text = None
                
                try:
                    old_container = driver.find_element(By.CSS_SELECTOR, "div[class*='tw:laptop:col-span-8']")
                except Exception:
                    old_container = None
                
                next_link[0].click()

                # Wait for actual content change, not just URL (AJAX pagination may not change URL)
                try:
                    # Check multiple indicators that page has changed
                    def page_has_changed(driver):
                        # Check 1: URL changed
                        if driver.current_url != prev_url:
                            return True
                        # Check 2: Old container went stale (detached from DOM)
                        if old_container:
                            try:
                                # Try to access a property - if stale, this will raise StaleElementReferenceException
                                _ = old_container.tag_name
                            except:
                                return True  # Container is stale, page changed
                        # Check 3: Page indicator text changed
                        if prev_page_text:
                            try:
                                new_indicator = driver.find_element(By.CSS_SELECTOR, "span[class*='tw:font-bold']")
                                if new_indicator.text != prev_page_text:
                                    return True
                            except:
                                pass
                        return False
                    
                    # Wait for page change (shorter timeout since pages load quickly)
                    WebDriverWait(driver, 4).until(page_has_changed)
                    
                    # Now wait for new content to be ready (short wait)
                    WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='tw:laptop:col-span-8']"))
                    )
                    
                    print(" >> Page loaded successfully.")
                    
                    # Scrape the new page
                    current_url = driver.current_url
                    if current_url != last_url or last_container is None:
                        last_container = navigate_page(driver, body_type, all_rows, category_rows)
                        if last_container:
                            last_url = current_url
                except TimeoutException:
                    # Page might have loaded but our checks didn't catch it - try scraping anyway
                    try:
                        # Quick check if container exists and page indicator changed
                        test_container = driver.find_element(By.CSS_SELECTOR, "div[class*='tw:laptop:col-span-8']")
                        current_url = driver.current_url
                        
                        # Check if page indicator changed (even if URL didn't)
                        page_changed = False
                        if prev_page_text:
                            try:
                                new_indicator = driver.find_element(By.CSS_SELECTOR, "span[class*='tw:font-bold']")
                                if new_indicator.text != prev_page_text:
                                    page_changed = True
                            except:
                                pass
                        
                        # Scrape if URL changed OR page indicator changed
                        if current_url != last_url or page_changed:
                            print(" >> Timeout on wait but content available, scraping...")
                            last_container = navigate_page(driver, body_type, all_rows, category_rows)
                            if last_container:
                                last_url = current_url
                        else:
                            print(" >> Page appears unchanged, continuing...")
                    except Exception:
                        print(" >> Page not ready yet, will retry...")
                        sleep(0.5)  # Brief wait before retry

            else:
                print("No link found. Must be last page of category.")
                # Category finished; write its CSV now.
                rows_for_category = category_rows.get(body_type, [])
                if rows_for_category:
                    safe_name = body_type.lower().replace(" ", "_")
                    write_rows_to_csv(rows_for_category, filepath=f"car_listings_{safe_name}.csv")
                    print(f"Saved {len(rows_for_category)} listings to car_listings_{safe_name}.csv")
                break

        except Exception as e:
            print(f"Skip page because of error: {e}")
            break

def navigate_page(driver, body_type, all_rows, category_rows):
    if not hasattr(navigate_page, "count"):
        navigate_page.count = 0
    
    # Quick captcha check (non-blocking if already past)
    try:
        bypass_captcha(driver)
    except Exception:
        pass  # Continue even if captcha check has issues
    
    try:
        # Reduced timeout - page should load faster after URL change
        page_car_listing_container = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='tw:laptop:col-span-8']"))
        )
        # Only increment page count once a real listing container is present.
        navigate_page.count += 1
        print(f"Navigating page {navigate_page.count} in {driver.title}")
        # Get list of all car_listings to scrape data
        car_listings = page_car_listing_container.find_elements(By.CSS_SELECTOR,
                "div[class*='tw:flex'][class*='tw:p-6']")
        if not car_listings:
            print("No car listing found.")
        else:
            print(f"Found {len(car_listings)} car listings on this page.")
            for car_listing in car_listings:
                extract_data_from_listing(car_listing, body_type, all_rows, category_rows)
        return page_car_listing_container
    except (NoSuchElementException, TimeoutException):
        # Don't print error - page might still be loading, will retry
        return None
    except Exception as e:
        # Only print actual errors, not timeouts
        print(f"(Error navigating page: {e})")
        return None

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
        sleep(1)  # Reduced wait time for popup to disappear

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

    max_wait = 10  # Reduced wait time - most redirects happen quickly
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

        # Wait and check again (shorter sleep for faster checks)
        if elapsed > 3:  # Only print after 3 seconds
            print(f" >> Waiting for page redirect: ({int(elapsed)}s)")
        time.sleep(1)  # Reduced from 2 to 1 second

def extract_data_from_listing(car_listing, body_type, all_rows, category_rows):
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

    color_raw = car_listing.find_element(By.CSS_SELECTOR,
                                     "span[class*='tw:text-sm tw:font-bold']").text
    color = normalize_color(color_raw)

    row = {
        "year": year,
        "make": make,
        "model": model,
        "price": price,
        "mileage": car_mileage,
        "color": color,
        "url": href_link,
        "body_type": body_type
    }
    all_rows.append(row)
    category_rows[body_type].append(row)

def normalize_color(raw_color):
    """Pick the basic color term already present in the descriptive color text."""
    color_str = (raw_color or "").lower()
    basic_colors = [
        "black", "white", "red", "blue", "green", "yellow",
        "orange", "purple", "pink", "brown", "beige", "gray",
        "grey", "silver", "gold"
    ]

    for base in basic_colors:
        if base in color_str:
            # Normalize grey/gray to Gray
            if base in ("gray", "grey"):
                return "gray"
            return base

    return raw_color.split()[0].lower() if raw_color else "Other"

def write_rows_to_csv(rows, filepath="car_listings.csv"):
    fieldnames = ["year", "make", "model", "price", "mileage", "color", "url", "body_type"]
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def write_category_csvs(category_rows, base_dir=".", prefix="car_listings"):
    """Write one CSV per category plus keep the already-written aggregate file."""
    fieldnames = ["year", "make", "model", "price", "mileage", "color", "url", "body_type"]
    for category, rows in category_rows.items():
        safe_name = category.lower().replace(" ", "_")
        filepath = f"{base_dir}/{prefix}_{safe_name}.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

if __name__ == "__main__":
    main()