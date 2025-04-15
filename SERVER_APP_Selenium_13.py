import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# Initialize the WebDriver
def init_driver():
    """Initialize Selenium WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run browser in headless mode (optional)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver


# Function to scrape all companies across paginated pages
def get_all_companies(query):
    """Scrape all companies' data from paginated pages."""
    url = f'https://www.example.com/search?q={query}'  # Replace with the actual URL structure
    driver = init_driver()
    driver.get(url)

    all_companies = []
    page_number = 1

    while True:
        print(f"Scraping page {page_number}")

        # Wait for the page to load completely
        time.sleep(3)

        # Scrape company data on the current page
        companies_on_page = driver.find_elements(By.CSS_SELECTOR, '.company-list-item')  # Adjust CSS selector as needed

        for company in companies_on_page:
            try:
                company_name = company.find_element(By.CSS_SELECTOR, '.company-name').text  # Adjust CSS selector
                company_number = company.find_element(By.CSS_SELECTOR, '.company-number').text  # Adjust CSS selector
                # Add the company data to the list
                all_companies.append({
                    'Company Name': company_name,
                    'Company Number': company_number,
                })
            except Exception as e:
                print(f"Error extracting company data: {e}")

        # Check if there's a "next" button for pagination
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '.govuk-pagination__link--next')
            if next_button.is_enabled():
                # Click the "next" button to go to the next page
                next_button.click()
                page_number += 1
            else:
                break  # No more pages, stop the loop
        except Exception as e:
            print(f"No next page found or error: {e}")
            break

    driver.quit()
    return all_companies


# Function to export data to Excel
def export_to_excel(companies, filename):
    """Export company data to Excel."""
    df = pd.DataFrame(companies)
    filepath = f"./{filename}.xlsx"
    df.to_excel(filepath, index=False)
    return filepath


# Main logic
if __name__ == "__main__":
    query = 'kings'  # Replace with your query or input from the user
    companies = get_all_companies(query)

    if companies:
        filename = f"{query}_companies"
        filepath = export_to_excel(companies, filename)
        print(f"Data exported to {filepath}")
    else:
        print("No companies found.")
