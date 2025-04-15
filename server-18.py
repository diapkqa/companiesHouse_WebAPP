import csv
import os
import hashlib
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
from openpyxl import Workbook
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
            nature_of_business["Description"] = "N/A"

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

@app.route('/export', methods=['GET'])
def export_data():
    """Exports all company data for a search term across all pages."""
    file_type = request.args.get("file_type")  # Either 'csv' or 'excel'
    search_term = request.args.get("search_term")

    if not search_term or file_type not in ["csv", "excel"]:
        return jsonify({"error": "Invalid data or file type"}), 400

    # Accumulate all company data from all pages
    companies = []
    page = 1
    limit = 10

    while True:
        data = fetch_companies(search_term, page, limit)
        if data and data.get('items'):
            for company in data['items']:
                companies.append((company))
            page += 1
        else:
            break

    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Generate CSV or Excel
    if file_type == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=companies[0].keys())
        writer.writeheader()
        writer.writerows(companies)
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{search_term}_companies.csv"
        )
    elif file_type == "excel":
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.append(list(companies[0].keys()))
        for company in companies:
            ws.append(list(company.values()))
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{search_term}_companies.xlsx"
        )


if __name__ == '__main__':
    app.run(debug=True)

