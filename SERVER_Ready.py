import os
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 20  # Number of results per page
os.makedirs(CACHE_DIR, exist_ok=True)

# Thread-safe list
lock = threading.Lock()
all_companies = []


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API."""
    start_index = (page - 1) * LIMIT
    url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"

    try:
        response = requests.get(url, auth=(API_KEY, ""))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching companies: {e}")
        return None


def fetch_company_details(company_number):
    """Fetch detailed company data from Companies House API."""
    url = f"{BASE_URL}/company/{company_number}"

    try:
        response = requests.get(url, auth=(API_KEY, ""))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching details for company {company_number}: {e}")
        return {}


def fetch_companies_details_concurrently(company_numbers):
    """Fetch company details concurrently."""
    detailed_companies = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_company = {executor.submit(fetch_company_details, cn): cn for cn in company_numbers}
        for future in as_completed(future_to_company):
            try:
                company_details = future.result()
                if company_details:
                    detailed_companies.append(company_details)
            except Exception as e:
                print(f"Error processing company {future_to_company[future]}: {e}")
    return detailed_companies


def parse_company_details(company_data):
    """Parse detailed company data into a standardised format."""
    try:
        company_info = {
            "Company Name": company_data.get("company_name", "N/A"),
            "Company Number": company_data.get("company_number", "N/A"),
            "Registered Office Address": company_data.get("registered_office_address", {}).get("address_line_1", "N/A"),
            "Company Type": company_data.get("type", "N/A"),
            "Company Status": company_data.get("company_status", "N/A"),
            "Incorporated Date": company_data.get("date_of_creation", "N/A"),
        }

        accounts = company_data.get("accounts", {})
        confirmation_statement = company_data.get("confirmation_statement", {})

        company_info.update({
            "Accounts Next Statement Date": accounts.get("next_accounts", {}).get("period_end_on", "N/A"),
            "Accounts Due Date": accounts.get("next_due", "N/A"),
            "Accounts Last Statement Date": accounts.get("last_accounts", {}).get("made_up_to", "N/A"),
            "Confirmation Next Statement Date": confirmation_statement.get("next_made_up_to", "N/A"),
            "Confirmation Due Date": confirmation_statement.get("next_due", "N/A"),
            "Confirmation Last Statement Date": confirmation_statement.get("last_made_up_to", "N/A"),
        })

        sic_codes = company_data.get("sic_codes", [])
        company_info["Nature of Business"] = ", ".join(sic_codes) if sic_codes else "N/A"

        previous_names = company_data.get("previous_names", [])
        company_info["Previous Company Names"] = ", ".join(
            [f"{name['name']} (Start: {name.get('start_date', 'N/A')}, End: {name.get('end_date', 'N/A')})" for name in
             previous_names]
        ) if previous_names else "N/A"

        return company_info
    except Exception as e:
        print(f"Error parsing company details: {e}")
        return {}


@app.route('/api/search', methods=['GET'])
def search_companies():
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', '1').strip() or 1)

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    data = fetch_companies(query, page)
    if not data or 'items' not in data:
        return jsonify({"error": "No companies found"}), 404

    company_numbers = [item["company_number"] for item in data['items'] if "company_number" in item]
    if not company_numbers:
        return jsonify({"error": "No valid company numbers found"}), 404

    detailed_companies = fetch_companies_details_concurrently(company_numbers)
    parsed_details = [parse_company_details(c) for c in detailed_companies if c]

    return jsonify(parsed_details)


@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    page = 1
    all_companies.clear()
    company_numbers = []

    while True:
        data = fetch_companies(query, page)
        if not data or 'items' not in data or not data['items']:
            break
        company_numbers.extend([item["company_number"] for item in data['items'] if "company_number" in item])
        if len(data['items']) < LIMIT:
            break
        page += 1

    if not company_numbers:
        return jsonify({"error": "No companies found"}), 404

    with ThreadPoolExecutor(max_workers=10) as executor:
        fetched_details = executor.map(fetch_company_details, company_numbers)

    valid_details = [parse_company_details(c) for c in fetched_details if c]
    if not valid_details:
        return jsonify({"error": "No valid company details found"}), 404

    df = pd.DataFrame(valid_details)
    export_path = os.path.join(CACHE_DIR, f"{query}_companies.xlsx")
    try:
        df.to_excel(export_path, index=False, engine='openpyxl')
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        return jsonify({"error": "Failed to save Excel file"}), 500

    return send_file(export_path, as_attachment=True, download_name=f"{query}_companies.xlsx")


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
