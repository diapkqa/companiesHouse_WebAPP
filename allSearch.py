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
    start_index = (page - 1)
    url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}"
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

        # Fetch accounts information
        accounts = {
            "AccountsNextStatementDate": "N/A",
            "AccountsDueDate": "N/A",
            "AccountsLastStatementDate": "N/A",
            "AccountsOverdue": "N/A"
        }
        if "accounts" in company_data:
            accounts_data = company_data["accounts"]
            accounts["AccountsNextStatementDate"] = accounts_data.get("next_accounts", "N/A")
            accounts["AccountsDueDate"] = accounts_data.get("next_due", "N/A")
            accounts["AccountsLastStatementDate"] = accounts_data.get("last_accounts", "N/A")

            # Check if 'next_due' and 'due_on' exist and compare for overdue status
            if "next_due" in accounts_data and "due_on" in accounts_data:
                if accounts_data["next_due"] < accounts_data["due_on"]:
                    accounts["AccountsOverdue"] = "Yes"
                else:
                    accounts["AccountsOverdue"] = "No"

        # Fetch confirmation statement information
        confirmation_statement = {
            "ConfirmationNextStatementDate": "N/A",
            "ConfirmationDueDate": "N/A",
            "ConfirmationLastStatementDate": "N/A",
            "ConfirmationOverdue": "N/A",
        }
        if "confirmation_statement" in company_data:
            confirmation_statement_data = company_data["confirmation_statement"]
            confirmation_statement["ConfirmationNextStatementDate"] = confirmation_statement_data.get("next_made_up_to", "N/A")
            confirmation_statement["ConfirmationDueDate"] = confirmation_statement_data.get("next_due", "N/A")
            confirmation_statement["ConfirmationLastStatementDate"] = confirmation_statement_data.get("last_made_up_to", "N/A")

            # Check if 'next_due' and 'due_on' exist and compare for overdue status
            if "next_due" in confirmation_statement_data and "due_on" in confirmation_statement_data:
                if confirmation_statement_data["next_due"] < confirmation_statement_data["due_on"]:
                    confirmation_statement["ConfirmationOverdue"] = "Yes"
                else:
                    confirmation_statement["ConfirmationOverdue"] = "No"

        # Fetch SIC codes (Nature of business)
        nature_of_business = {"siCode": "N/A", "Description": "N/A"}
        if "sic_codes" in company_data and company_data["sic_codes"]:
            sic_code = company_data["sic_codes"][0]
            nature_of_business["siCode"] = sic_code
            # Description might not be available directly via the API, so we leave it as "N/A"
            nature_of_business["Description"] = "N/A"

        # Fetch previous company names
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

@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export all companies' data to Excel/CSV based on query."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    all_companies = []
    page = 1
    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    company_details = fetch_company_details(company_number)
                    all_companies.append(company_details)

            # Check if there is more data to fetch (pagination)
            if len(data['items']) < LIMIT:
                break
            page += 1
        else:
            break

    # Create a DataFrame
    if all_companies:
        company_data = []
        for company in all_companies:
            company_data.append({
                "Company Name": company.get("companyInfo", {}).get("companyName", "N/A"),
                "Company Number": company.get("companyInfo", {}).get("companyNumber", "N/A"),
                "Registered Office Address": company.get("companyDetails", {}).get("RegisteredOfficeAddress", "N/A"),
                "Company Type": company.get("companyDetails", {}).get("CompanyType", "N/A"),
                "Company Status": company.get("companyDetails", {}).get("CompanyStatus", "N/A"),
                "Incorporated Date": company.get("companyDetails", {}).get("IncorporatedDate", "N/A"),
                "Accounts Next Statement Date": company.get("accounts", {}).get("AccountsNextStatementDate", "N/A"),
                "Accounts Due Date": company.get("accounts", {}).get("AccountsDueDate", "N/A"),
                "Accounts Last Statement Date": company.get("accounts", {}).get("AccountsLastStatementDate", "N/A"),
                "Accounts Overdue": company.get("accounts", {}).get("AccountsOverdue", "N/A"),
                "Confirmation Next Statement Date": company.get("confirmationStatement", {}).get("ConfirmationNextStatementDate", "N/A"),
                "Confirmation Due Date": company.get("confirmationStatement", {}).get("ConfirmationDueDate", "N/A"),
                "Confirmation Last Statement Date": company.get("confirmationStatement", {}).get("ConfirmationLastStatementDate", "N/A"),
                "Confirmation Overdue": company.get("confirmationStatement", {}).get("ConfirmationOverdue", "N/A"),
                "SIC Code": company.get("natureOfBusiness", {}).get("siCode", "N/A"),
                "Business Description": company.get("natureOfBusiness", {}).get("Description", "N/A"),
            })

        df = pd.DataFrame(company_data)

        # Save the DataFrame to Excel or CSV
        file_path = './exported_companies.xlsx'
        df.to_excel(file_path, index=False)  # Change to .csv for CSV format
        return send_file(file_path, as_attachment=True, download_name="companies.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # return send_file(file_path, as_attachment=True)

    return jsonify({"error": "No data found to export"}), 404

if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
