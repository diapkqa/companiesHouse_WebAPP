import os
import threading
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from bs4 import BeautifulSoup

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
# Advance_URL="https://api.company-information.service.gov.uk/search/companies?q=a&items_per_page=20&start_index=100"
CACHE_DIR = './cache'
LIMIT = 20  # Number of results per page

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Thread-safe list for storing company details
lock = threading.Lock()
all_companies = []

app = Flask(__name__)
CORS(app)

def fetch_company_details(company_number):
    """Fetch detailed company data from Companies House API."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        company_data = response.json()

        # Basic Company Info
        company_info = {
            "companyName": company_data.get("company_name", "N/A"),
            "companyNumber": company_data.get("company_number", "N/A"),
        }

        # Company Details
        company_details = {
            "RegisteredOfficeAddress": company_data.get("registered_office_address", {}).get("address_line_1", "N/A"),
            "CompanyType": company_data.get("type", "N/A"),
            "CompanyStatus": company_data.get("company_status", "N/A"),
            "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        }

        # Accounts Information
        accounts = {
            "AccountsNextStatementDate": "N/A",
            "AccountsDueDate": "N/A",
            "AccountsLastStatementDate": "N/A"
        }
        if "accounts" in company_data:
            accounts_data = company_data["accounts"]
            accounts["AccountsNextStatementDate"] = accounts_data.get("next_accounts", {}).get("period_end_on", "N/A")
            accounts["AccountsDueDate"] = accounts_data.get("next_due", "N/A")
            accounts["AccountsLastStatementDate"] = accounts_data.get("last_accounts", {}).get("period_end_on", "N/A")

        # Confirmation Statement
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

        # Nature of Business
        nature_of_business = []
        if "sic_codes" in company_data and company_data["sic_codes"]:
            for sic_code in company_data["sic_codes"][:4]:
                nature_of_business.append({
                    "sicCode": sic_code,
                    "Description": "N/A"
                })
        else:
            nature_of_business.append({
                "sicCode": "N/A",
                "Description": "N/A"
            })

        # Previous Company Names
        previous_names = []
        if "previous_names" in company_data:
            for name in company_data["previous_names"]:
                previous_names.append({
                    "name": name.get("company_name", "N/A"),
                    "startPrevNameDate": name.get("start_date", "N/A"),
                    "endPrevNameDate": name.get("end_date", "N/A"),
                })

        # Add to the all_companies list safely
        with lock:
            all_companies.append({
                "companyInfo": company_info,
                "companyDetails": company_details,
                "accounts": accounts,
                "confirmationStatement": confirmation_statement,
                "natureOfBusiness": nature_of_business,
                "previousCompanyNames": previous_names,
            })


    else:
        return None


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API."""
    start_index = (page - 1) * LIMIT
    url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json()
    return None


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name or SIC code."""
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', '1').strip())

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    try:
        data = fetch_companies(query, page)
        print(f"API Response Data: {data}")  # Debug print
        if data and 'items' in data:
            if not data['items']:
                return jsonify({"message": "No companies found matching the query"}), 404

            detailed_companies = []
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    company_details = fetch_company_details(company_number)
                    detailed_companies.append(company_details)

            return jsonify({
                "message": "Companies fetched successfully...",
                "data": detailed_companies
            }), 200
        else:
            return jsonify({"error": "No companies found"}), 404
    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500



@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    """Export all searched companies to an Excel file."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    page = 1
    all_companies.clear()

    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            company_numbers = [company.get("company_number") for company in data['items'] if company.get("company_number")]
            if not company_numbers:
                break

            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(fetch_company_details, company_numbers)

            if len(data['items']) < LIMIT:
                break
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found to export"}), 404

    df = pd.DataFrame(all_companies)
    file_path = os.path.join(os.getcwd(), "exported_companies.xlsx")
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


"""---SEARCH BY SIC CODES---"""

@app.route('/api/search-by-sic', methods=['GET'])
def search_companies_by_sic():
    """Search companies by SIC code."""
    sic_code = request.args.get('sic_code', '').strip()
    page = int(request.args.get('page', '1').strip())

    if not sic_code:
        return jsonify({"error": "SIC code is required"}), 400

    try:
        start_index = (page - 1) * LIMIT
        url = f"{BASE_URL}/api/search-by-sic?q={sic_code}&items_per_page={LIMIT}&start_index={start_index}"
        response = requests.get(url, auth=(API_KEY, ""))

        if response.status_code != 200:

            return jsonify({"error": "Failed to fetch companies"}), response.status_code

        data = response.json()

        if 'items' in data and data['items']:
            detailed_companies = []
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    fetch_company_details(company_number)

            # Paginated response
            return jsonify({
                "message": "Companies fetched successfully",
                "data": all_companies[(page - 1) * LIMIT: page * LIMIT],
                "pagination": {
                    "currentPage": page,
                    "totalItems": len(all_companies),
                    "itemsPerPage": LIMIT,
                    "totalPages": (len(all_companies) + LIMIT - 1) // LIMIT,
                }
            }), 200
        else:
            return jsonify({"message": "No companies found"}), 404

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route('/api/export-by-sic', methods=['GET'])
def export_companies_by_sic():
    """Export companies searched by SIC code to Excel or CSV."""
    sic_code = request.args.get('sic_code', '').strip()

    if not sic_code:
        return jsonify({"error": "SIC code is required"}), 400

    page = 1
    all_companies.clear()

    while True:
        start_index = (page - 1) * LIMIT
        url = f"{BASE_URL}/search/companies?q={sic_code}&items_per_page={LIMIT}&start_index={start_index}"
        response = requests.get(url, auth=(API_KEY, ""))

        if response.status_code != 200:
            break

        data = response.json()

        if 'items' in data and data['items']:
            company_numbers = [company.get("company_number") for company in data['items'] if
                               company.get("company_number")]
            if not company_numbers:
                break

            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(fetch_company_details, company_numbers)

            if len(data['items']) < LIMIT:
                break
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Save results to an Excel or CSV file
    file_type = request.args.get('file_type', 'excel').strip().lower()
    file_name = f"exported_companies_by_sic.{file_type}"
    file_path = os.path.join(os.getcwd(), file_name)

    df = pd.DataFrame(all_companies)

    if file_type == 'csv':
        df.to_csv(file_path, index=False)
    else:
        df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@app.route('/api/download-button', methods=['POST'])
def download_button_action():

    return jsonify({"message": "Download button functionality needs to be integrated with Selenium"}), 501


if __name__ == '__main__':
    app.run(host='192.168.16.116', port=5000, debug=True)
