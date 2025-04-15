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


def fetch_all_companies(query):
    """Fetch all companies for a given query."""
    all_companies = []
    page = 1

    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            all_companies.extend(data['items'])
            if len(data['items']) < LIMIT:  # No more pages
                break
            page += 1
        else:
            break

    return all_companies


def fetch_company_details(company_number):
    """Fetch detailed company data from Companies House API."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        company_data = response.json()

        company_info = {
            "companyName": company_data.get("company_name", "N/A"),
            "companyNumber": company_data.get("company_number", "N/A"),
        }

        company_details = {
            "RegisteredOfficeAddress": company_data.get("registered_office_address", {}).get("address_line_1", "N/A"),
            "CompanyType": company_data.get("type", "N/A"),
            "CompanyStatus": company_data.get("company_status", "N/A"),
            "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        }

        accounts = {
            "AccountsNextStatementDate": company_data.get("accounts", {}).get("next_accounts", {}).get("period_start_on", "N/A"),
            "AccountsDueDate": company_data.get("accounts", {}).get("next_due", "N/A"),
            "AccountsLastStatementDate": company_data.get("accounts", {}).get("last_accounts", {}).get("period_end_on", "N/A"),
        }

        return {
            "companyInfo": company_info,
            "companyDetails": company_details,
            "accounts": accounts,
        }

    return {}


@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    """Fetch all companies and export data to Excel."""
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    companies = fetch_all_companies(query)

    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Process data into a DataFrame
    company_data = []
    for company in companies:
        company_number = company.get("company_number")
        if company_number:
            details = fetch_company_details(company_number)
            company_data.append({
                "Company Name": details["companyInfo"].get("companyName"),
                "Company Number": details["companyInfo"].get("companyNumber"),
                "Registered Office Address": details["companyDetails"].get("RegisteredOfficeAddress"),
                "Company Type": details["companyDetails"].get("CompanyType"),
                "Company Status": details["companyDetails"].get("CompanyStatus"),
                "Incorporated Date": details["companyDetails"].get("IncorporatedDate"),
                "Accounts Next Statement Date": details["accounts"].get("AccountsNextStatementDate"),
                "Accounts Due Date": details["accounts"].get("AccountsDueDate"),
                "Accounts Last Statement Date": details["accounts"].get("AccountsLastStatementDate"),
            })

    df = pd.DataFrame(company_data)

    # Save to Excel
    excel_file = os.path.join(CACHE_DIR, "companies_export.xlsx")
    df.to_excel(excel_file, index=False)

    return send_file(excel_file, as_attachment=True, download_name="companies_export.xlsx")


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
