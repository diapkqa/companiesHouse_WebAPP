import os
import hashlib
import json
import csv
import io
import requests
from flask import Flask, request, jsonify, send_file
from openpyxl import Workbook
from bs4 import BeautifulSoup

app = Flask(__name__)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 10  # Number of results per page

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API."""
    start_index = (page - 1) * LIMIT
    url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}&items_per_page={LIMIT}"
    cache_file = get_cache_file(query, page)

    # Check cache
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    # Fetch from API
    response = requests.get(url, auth=(API_KEY, ""))
    if response.status_code == 200:
        data = response.json()
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        return data
    else:
        return None


def extract_company_details(company_number):
    """Scrape detailed company data from Companies House webpage."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract company info
        company_info = {
            "companyName": soup.find("h1", class_="govuk-heading-l").text.strip() if soup.find("h1",
                                                                                               class_="govuk-heading-l") else "N/A",
            "companyNumber": soup.find("span", id="company-number").text.strip() if soup.find("span",
                                                                                              id="company-number") else "N/A",
        }

        # Extract company details
        company_details = {
            "RegisteredOfficeAddress": soup.find("dd", class_="text data").text.strip() if soup.find("dd",
                                                                                                     class_="text data") else "N/A",
            "CompanyType": soup.find("dd", id="company-type").text.strip() if soup.find("dd",
                                                                                        id="company-type") else "N/A",
            "CompanyStatus": soup.find("dd", id="company-status").text.strip() if soup.find("dd",
                                                                                            id="company-status") else "N/A",
            "IncorporatedDate": soup.find("dd", id="company-creation-date").text.strip() if soup.find("dd",
                                                                                                      id="company-creation-date") else "N/A",
        }

        # Extract account information
        accounts_section = soup.find("div", class_="column-half")
        accounts = {
            "AccountsNextStatementDate": "N/A",
            "AccountsDueDate": "N/A",
            "AccountsLastStatementDate": "N/A",
        }
        if accounts_section:
            accounts_texts = accounts_section.find_all("strong")
            if len(accounts_texts) >= 3:
                accounts["AccountsNextStatementDate"] = accounts_texts[0].text.strip()
                accounts["AccountsDueDate"] = accounts_texts[1].text.strip()
                accounts["AccountsLastStatementDate"] = accounts_texts[2].text.strip()

        # Extract confirmation statement information
        confirmation_section = soup.find_all("div", class_="column-half")[1] if len(
            soup.find_all("div", class_="column-half")) > 1 else None
        confirmation_statement = {
            "ConfirmationNextStatementDate": "N/A",
            "ConfirmationDueDate": "N/A",
            "ConfirmationLastStatementDate": "N/A",
        }
        if confirmation_section:
            confirmation_texts = confirmation_section.find_all("strong")
            if len(confirmation_texts) >= 3:
                confirmation_statement["ConfirmationNextStatementDate"] = confirmation_texts[0].text.strip()
                confirmation_statement["ConfirmationDueDate"] = confirmation_texts[1].text.strip()
                confirmation_statement["ConfirmationLastStatementDate"] = confirmation_texts[2].text.strip()

        # Extract SIC codes
        sic_section = soup.find("ul")
        nature_of_business = {"siCode": "N/A", "Description": "N/A"}
        if sic_section:
            sic_text = sic_section.find("span")
            if sic_text and " - " in sic_text.text:
                parts = sic_text.text.split(" - ")
                nature_of_business["siCode"] = parts[0].strip()
                nature_of_business["Description"] = parts[1].strip()

        # Extract previous company names
        previous_names = []
        previous_names_section = soup.find("h2", string="Previous company names")
        if previous_names_section:
            rows = soup.select("tbody tr")
            for row in rows:
                name_cell = row.find("td", id=lambda x: x and x.startswith("previous-name"))
                date_cell = row.find("td", id=lambda x: x and x.startswith("previous-date"))
                if name_cell and date_cell:
                    start_date, end_date = date_cell.text.strip().split("-")
                    previous_names.append({
                        "name": name_cell.text.strip(),
                        "startPrevNameDate": start_date.strip(),
                        "endPrevNameDate": end_date.strip(),
                    })

        return {
            "companyInfo": company_info,
            "companyDetails": company_details,
            "accounts": accounts,
            "confirmationStatement": confirmation_statement,
            "natureOfBusiness": nature_of_business,
            "previousCompanyNames": previous_names,
        }

    return {}


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    search_type = request.args.get('type', 'name').strip().lower()
    page = int(request.args.get('page', 1))

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    if search_type == "number":
        # Fetch company details by number
        company_details = extract_company_details(query)
        if company_details:
            return jsonify(company_details)
        else:
            return jsonify({"error": "Company not found"}), 404

    else:  # Default to name search
        data = fetch_companies(query, page)
        if data and 'items' in data:
            return jsonify(data['items'])
        else:
            return jsonify({"error": "No companies found"}), 404


if __name__ == '__main__':
    app.run(debug=True)
