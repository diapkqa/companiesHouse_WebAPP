import os
import hashlib
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"  #  with your API key
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API with pagination."""
    url = f"{BASE_URL}/search/companies"
    params = {"q": query, "start_index": (page - 1) * 20, "items_per_page": 20}
    cache_file = get_cache_file(query, page)

    # Check cache
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    # Fetch from API
    response = requests.get(url, params=params, auth=(API_KEY, ""))
    if response.status_code == 200:
        data = response.json()
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        return data
    else:
        print(f"Failed to fetch page {page}: {response.status_code}")
        return None


def fetch_all_companies(query):
    """Fetch all companies for the given query, across all pages."""
    all_companies = []  # List to store all companies
    start_index = 0
    items_per_page = 20

    while True:
        print(f"Fetching data: start_index={start_index}, items_per_page={items_per_page}")

        # Prepare API call with pagination
        url = f"{BASE_URL}/search/companies"
        params = {"q": query, "start_index": start_index, "items_per_page": items_per_page}

        response = requests.get(url, params=params, auth=(API_KEY, ""))

        if response.status_code != 200:
            print(f"Error: Failed to fetch data (status code: {response.status_code})")
            break  # Stop on error

        data = response.json()
        if "items" not in data or not data["items"]:
            break  # Stop when no more results are available

        # Append the fetched items to the list
        all_companies.extend(data["items"])

        # Stop if the number of items fetched is less than items_per_page (last page)
        if len(data["items"]) < items_per_page:
            break

        # Move to the next page
        start_index += items_per_page

    return all_companies


def fetch_company_details(company_number):
    """Fetch detailed company data from Companies House API."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        company_data = response.json()

        return {
            "companyName": company_data.get("company_name", "N/A"),
            "companyNumber": company_data.get("company_number", "N/A"),
            "companyStatus": company_data.get("company_status", "N/A"),
            "incorporatedDate": company_data.get("date_of_creation", "N/A"),
            "companyType": company_data.get("type", "N/A"),
            "registeredAddress": company_data.get("registered_office_address", {}).get("address_line_1", "N/A"),
            "sicCodes": company_data.get("sic_codes", "N/A"),
            "accountsDue": company_data.get("accounts", {}).get("next_due", "N/A"),
            "confirmationStatementDue": company_data.get("confirmation_statement", {}).get("next_due", "N/A")
        }

    return {"companyNumber": company_number, "error": "Failed to fetch details"}


def export_to_excel(companies, filename):
    """Export company details to an Excel file."""
    df = pd.DataFrame(companies)
    filepath = os.path.join(CACHE_DIR, filename)
    df.to_excel(filepath, index=False)
    return filepath


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies with pagination
    companies = fetch_all_companies(query)
    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Fetch detailed information for each company
    detailed_companies = []
    for company in companies:
        company_number = company.get("company_number")
        if company_number:
            details = fetch_company_details(company_number)
            detailed_companies.append(details)

    return jsonify(detailed_companies)


@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export all companies matching the query to an Excel file."""
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies matching the query
    companies = fetch_all_companies(query)
    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Fetch detailed company information
    detailed_companies = []
    for company in companies:
        company_number = company.get("company_number")
        if company_number:
            details = fetch_company_details(company_number)
            detailed_companies.append(details)

    if detailed_companies:
        filename = f"{query}_companies.xlsx"
        filepath = export_to_excel(detailed_companies, filename)
        return send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    return jsonify({"error": "No detailed company information found"}), 404


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
