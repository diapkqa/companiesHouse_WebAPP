import os
import string
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


def fetch_company_details(company_number):
    """Fetch detailed company data from Companies House API."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        company_data = response.json()

        company_info = {
            # "companyName": company_data.get("company_name", "N/A"),
            "Company Name": company_data.get("companyInfo", {}).get("companyName", "N/A"),

            "companyNumber": company_data.get("company_number", "N/A"),
        }

        company_details = {
            "RegisteredOfficeAddress": company_data.get("registered_office_address", {}).get("address_line_1", "N/A"),
            "CompanyType": company_data.get("type", "N/A"),
            "CompanyStatus": company_data.get("company_status", "N/A"),
            "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        }

        accounts = {
            "AccountsNextStatementDate": "N/A",
            "AccountsDueDate": "N/A",
            "AccountsLastStatementDate": "N/A"
        }
        if "accounts" in company_data:
            accounts_data = company_data["accounts"]
            accounts["AccountsNextStatementDate"] = accounts_data.get("next_accounts", "N/A")
            accounts["AccountsDueDate"] = accounts_data.get("next_due", "N/A")
            accounts["AccountsLastStatementDate"] = accounts_data.get("last_accounts", "N/A")

        confirmation_statement = {
            "ConfirmationNextStatementDate": "N/A",
            "ConfirmationDueDate": "N/A",
            "ConfirmationLastStatementDate": "N/A"
        }
        if "confirmation_statement" in company_data:
            confirmation_statement_data = company_data["confirmation_statement"]
            confirmation_statement["ConfirmationNextStatementDate"] = confirmation_statement_data.get("next_made_up_to", "N/A")
            confirmation_statement["ConfirmationDueDate"] = confirmation_statement_data.get("next_due", "N/A")
            confirmation_statement["ConfirmationLastStatementDate"] = confirmation_statement_data.get("last_made_up_to", "N/A")

        nature_of_business = {"siCode": "N/A", "Description": "N/A"}
        if "sic_codes" in company_data and company_data["sic_codes"]:
            sic_code = company_data["sic_codes"][0]
            nature_of_business["siCode"] = sic_code

        previous_names = []
        if "previous_names" in company_data:
            for name in company_data["previous_names"]:
                previous_names.append({
                    "name": name.get("company_name", "N/A"),
                    "startPrevNameDate": name.get("start_date", "N/A"),
                    "endPrevNameDate": name.get("end_date", "N/A"),
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

    data = fetch_companies(query, page)
    if data and 'items' in data:
        # Fetch detailed information for each company
        detailed_companies = []
        for company in data['items']:
            company_number = company.get("company_number")
            if company_number:
                company_details = fetch_company_details(company_number)
                detailed_companies.append(company_details)

        if detailed_companies:
            return jsonify(detailed_companies)
        else:
            return jsonify({"error": "No detailed company information found"}), 404
    else:
        return jsonify({"error": "No companies found"}), 404


@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export all search results to an Excel or CSV file."""
    query = request.args.get('query', '').strip()
    search_type = request.args.get('type', 'name').strip().lower()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    page = 1
    all_companies = []

    # Fetch and accumulate data across all pages
    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            detailed_companies = []
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    company_details = fetch_company_details(company_number)
                    detailed_companies.append(company_details)
            all_companies.extend(detailed_companies)
            if len(data['items']) < LIMIT:  # End of data (no more pages)
                break
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found"}), 404

    # Convert to pandas DataFrame
    company_data = []
    for company in all_companies:
        company_data.append({
            "Company Name": company["companyInfo"].get("companyName", "N/A"),
            "Company Number": company["companyInfo"].get("companyNumber", "N/A"),
            "Company Type": company["companyDetails"].get("CompanyType", "N/A"),
            "Company Status": company["companyDetails"].get("CompanyStatus", "N/A"),
            "Incorporated Date": company["companyDetails"].get("IncorporatedDate", "N/A"),
            "Registered Office Address": company["companyDetails"].get("RegisteredOfficeAddress", "N/A"),
            "Accounts Next Statement Date": company["accounts"].get("AccountsNextStatementDate", "N/A"),
            "Accounts Due Date": company["accounts"].get("AccountsDueDate", "N/A"),
            "Accounts Last Statement Date": company["accounts"].get("AccountsLastStatementDate", "N/A"),
            "Confirmation Next Statement Date": company["confirmationStatement"].get("ConfirmationNextStatementDate", "N/A"),
            "Confirmation Due Date": company["confirmationStatement"].get("ConfirmationDueDate", "N/A"),
            "Confirmation Last Statement Date": company["confirmationStatement"].get("ConfirmationLastStatementDate", "N/A"),
            "SIC Code": company["natureOfBusiness"].get("siCode", "N/A"),
        })

    df = pd.DataFrame(company_data)

    # Save the data to Excel or CSV
    output_file = 'companies_data.xlsx'
    df.to_excel(output_file, index=False)

    # Optionally, for CSV export:
    # output_file = 'companies_data.csv'
    # df.to_csv(output_file, index=False)

    return send_file(output_file, as_attachment=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
