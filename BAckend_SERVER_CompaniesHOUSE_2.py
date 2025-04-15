import os
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
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

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Thread-safe list to store all company details
lock = threading.Lock()
all_companies = []

def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")

"""---Fetch Companies---"""

#
# def fetch_companies(query, sic_code=None, page=1):
#     """Fetch companies from Companies House API with SIC code support."""
#     start_index = (page - 1) * LIMIT  # Calculate the starting index
#     if sic_code:
#         url = f"{BASE_URL}/search/companies?q={query}&sicCodes={sic_code}&items_per_page={LIMIT}&start_index={start_index}"
#     else:
#         url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"
#
#     print(f"Requesting URL: {url}")  # Debugging line to verify request URL
#
#     response = requests.get(url, auth=(API_KEY, ""))
#
#     if response.status_code == 200:
#         data = response.json()
#         print(f"Received {len(data.get('items', []))} companies on page {page}")  # Debug: Print number of items
#         return data
#     else:
#         print("Error fetching data:", response.text)
#         return None






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

        nature_of_business = []
        if "sic_codes" in company_data and company_data["sic_codes"]:
            for sic_code in company_data["sic_codes"][:4]:
                nature_of_business.append({
                    "sicCode": sic_code,
                    "Description": "N/A"
                })
        else:
            nature_of_business.append({"sicCode": "N/A", "Description": "N/A"})

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

"""---Search Companies---"""

# @app.route('/api/search', methods=['GET'])
# def search_companies():
#     """Search companies by name, number, or SIC code."""
#     query = request.args.get('query', '').strip()
#     sic_code = request.args.get('sicCode', '').strip()  # Get SIC code parameter
#     page_param = request.args.get('page', '1').strip()  # Get page parameter
#
#     # Validate page parameter
#     if not page_param.isdigit():
#         return jsonify({"error": "Invalid page number"}), 400
#
#     page = int(page_param)
#
#     if not query and not sic_code:
#         return jsonify({"error": "Search term (name/number) or SIC code is required"}), 400
#
#     data = fetch_companies(query, sic_code, page)
#     if data and 'items' in data:
#         # Fetch detailed information for each company
#         detailed_companies = []
#         for company in data['items']:
#             company_number = company.get("company_number")
#             if company_number:
#                 company_details = fetch_company_details(company_number)
#                 detailed_companies.append(company_details)
#
#         if detailed_companies:
#             return jsonify({
#                 "message": "Companies fetched successfully...",
#                 "data": detailed_companies
#             })
#         else:
#             return jsonify({"error": "No detailed company information found"}), 404
#     else:
#         return jsonify({"error": "No companies found"}), 404


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    sic_code = request.args.get('sicCode', '').strip()  # Fetch SIC code from query params
    page_param = request.args.get('page', '1').strip()  # Get page parameter as string

    # Validate page parameter
    if not page_param.isdigit():
        return jsonify({"error": "Invalid page number"}), 400

    page = int(page_param)

    if not query and not sic_code:
        return jsonify({"error": "Search term (company name or SIC code) is required"}), 400

    data = fetch_companies(query, sic_code, page)
    if data and 'items' in data:
        # Fetch detailed information for each company
        detailed_companies = []
        for company in data['items']:
            company_number = company.get("company_number")
            if company_number:
                company_details = fetch_company_details(company_number)
                detailed_companies.append(company_details)

        if detailed_companies:
            return jsonify({
                "message": "Companies fetched successfully...",
                "data": detailed_companies
            })
        else:
            return jsonify({"error": "No detailed company information found"}), 404
    else:
        return jsonify({"error": "No companies found"}), 404


def fetch_companies(query, sic_code=None, page=1):
    """Fetch companies from Companies House API with SIC code support."""
    start_index = (page - 1) * LIMIT  # Calculate the starting index

    if sic_code:
        # Use the advanced search URL for SIC code-based search
        url = f"https://find-and-update.company-information.service.gov.uk/advanced-search/get-results={query}&sicCodes={sic_code}&items_per_page={LIMIT}&start_index={start_index}"
    else:
        # Use the standard search URL for name or number-based search
        url = f"https://api.company-information.service.gov.uk/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"

        #https://find-and-update.company-information.service.gov.uk/advanced-search/get-results?sicCodes=62020&items_per_page=20&start_index=0

    print(f"Requesting URL: {url}")  # Debugging line to verify request URL

    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        data = response.json()
        print(f"Received {len(data.get('items', []))} companies on page {page}")  # Debug: Print number of items
        return data
    else:
        print("Error fetching data:", response.text)
        return None


@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    """Export all searched companies to an Excel file with pagination."""
    query = request.args.get('query', '').strip()
    sic_code = request.args.get('sicCode', '').strip()
    page = 1
    all_companies.clear()

    if not query and not sic_code:
        return jsonify({"error": "Search term (company name or SIC code) is required"}), 400

    company_numbers = []
    while True:
        try:
            data = None
            if sic_code:
                data = fetch_companies(sic_code, page, sic_code=True)
            else:
                data = fetch_companies(query, page)

            if data and 'items' in data:
                company_numbers.extend([company.get("company_number") for company in data['items'] if company.get("company_number")])
                if len(data['items']) < LIMIT:
                    break
                page += 1
            else:
                break
        except Exception as e:
            print(f"Error fetching companies for query '{query}' on page {page}: {e}")
            break

    if not company_numbers:
        return jsonify({"error": "No companies found to export"}), 404

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(fetch_and_store_company_details, company_numbers)

    company_rows = []
    for company in all_companies:
        try:
            company_rows.append({
                "Company Name": company.get("companyInfo", {}).get("companyName", "N/A"),
                "Company Number": company.get("companyInfo", {}).get("companyNumber", "N/A"),
                "Registered Office Address": company.get("companyDetails", {}).get("RegisteredOfficeAddress", "N/A"),
                "Company Type": company.get("companyDetails", {}).get("CompanyType", "N/A"),
                "Company Status": company.get("companyDetails", {}).get("CompanyStatus", "N/A"),
                "Incorporated Date": company.get("companyDetails", {}).get("IncorporatedDate", "N/A"),
                "Accounts Next Statement Date": company.get("accounts", {}).get("AccountsNextStatementDate", "N/A"),
                "Accounts Due Date": company.get("accounts", {}).get("AccountsDueDate", "N/A"),
                "Accounts Last Statement Date": company.get("accounts", {}).get("AccountsLastStatementDate", "N/A"),
                "Confirmation Next Statement Date": company.get("confirmationStatement", {}).get("ConfirmationNextStatementDate", "N/A"),
                "Confirmation Due Date": company.get("confirmationStatement", {}).get("ConfirmationDueDate", "N/A"),
                "Confirmation Last Statement Date": company.get("confirmationStatement", {}).get("ConfirmationLastStatementDate", "N/A"),
                "Nature of Business": ", ".join([f"{entry.get('sicCode', 'N/A')}: {entry.get('Description', 'N/A')}" for entry in company.get("natureOfBusiness", [])]),
                "Previous Company Names": ", ".join([f"{name.get('name', 'N/A')} (Start: {name.get('startPrevNameDate', 'N/A')}, End: {name.get('endPrevNameDate', 'N/A')})" for name in company.get("previousCompanyNames", [])]),
            })
        except Exception as e:
            print(f"Error processing company data: {e}")

    if not company_rows:
        return jsonify({"error": "No valid company details to export"}), 500

    df = pd.DataFrame(company_rows)
    export_file_path = os.path.join(CACHE_DIR, f"{query}_companies.xlsx")
    try:
        df.to_excel(export_file_path, index=False)
        return send_file(export_file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": f"Error exporting to Excel: {e}"}), 500

def fetch_and_store_company_details(company_number):
    """Fetch company details and store them in a shared list."""
    company_details = fetch_company_details(company_number)
    with lock:
        all_companies.append(company_details)

if __name__ == '__main__':
    app.run(host='192.168.1.119',port=5000,debug=True)
