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
LIMIT = 20  # Number of results per page

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API."""
    start_index = (page - 1) * LIMIT  # Calculate the starting index
    url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"
    print(f"Requesting URL: {url}")  # Debugging line to verify request URL

    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        data = response.json()
        print(f"Received {len(data.get('items', []))} companies on page {page}")  # Debug: Print number of items
        return data
    else:
        print("Error fetching data:", response.text)
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
            "AccountsLastStatementDate": "N/A"
        #     "AccountsOverdue": "N/A",
         }
        if "accounts" in company_data:
            accounts_data = company_data["accounts"]
            accounts["AccountsNextStatementDate"] = accounts_data.get("next_accounts", "N/A")
            accounts["AccountsDueDate"] = accounts_data.get("next_due", "N/A")

            # if accounts["isDue"] =  accounts["AccountsDueDate"]

            accounts["AccountsLastStatementDate"] = accounts_data.get("last_accounts", "N/A")

            # Check if 'next_due' and 'due_on' exist and compare for overdue status
            if "next_due" in accounts_data and "due_on" in accounts_data:
                if accounts_data["next_due"] < accounts_data["due_on"]:
                    accounts["AccountsOverdue"] = "Yes"
                else:
                    accounts["AccountsOverdue"] = "No"
            # else:
            #     accounts["AccountsOverdue"] = "N/A"

        # Fetch confirmation statement information
        confirmation_statement = {
            "ConfirmationNextStatementDate": "N/A",
            "ConfirmationDueDate": "N/A",
            "ConfirmationLastStatementDate": "N/A"
            # "ConfirmationOverdue": "N/A",
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



        nature_of_business = []

        if "sic_codes" in company_data and company_data["sic_codes"]:
            # Iterate over the first 4 SIC codes, or fewer if there are less than 4
            for sic_code in company_data["sic_codes"][:4]:
                nature_of_business.append({
                    "sicCode": sic_code,
                    "Description": "N/A"  # Replace "N/A" with actual descriptions if available
                })
        else:
            # Default entry if no SIC codes are available
            nature_of_business.append({
                "sicCode": "N/A",
                "Description": "N/A"
            })

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

def export_to_file(companies, filename, file_type='excel'):
    """Export company details to an Excel (.xls) or CSV file."""
    df = pd.DataFrame(companies)

    # Ensure correct file extension
    if file_type == 'excel':
        if not filename.endswith('.xls'):  # Add '.xls' if not present
            filename += '.xls'
        filepath = os.path.join(CACHE_DIR, filename)
        df.to_excel(filepath, index=False, engine='xlwt')  # Use xlwt engine for .xls
    elif file_type == 'csv':
        if not filename.endswith('.csv'):  # Add '.csv' if not present
            filename += '.csv'
        filepath = os.path.join(CACHE_DIR, filename)
        df.to_csv(filepath, index=False)

    return filepath


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name and display 20 companies per page."""
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', 1))

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch companies for the requested page
    data = fetch_companies(query, page)
    if data and 'items' in data:
        return jsonify(data['items'])  # Return 20 companies
    else:
        return jsonify({"error": "No companies found"}), 404


from concurrent.futures import ThreadPoolExecutor, as_completed

@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export all companies across all pages to an Excel or CSV file (Optimised with parallel requests)."""
    query = request.args.get('query', '').strip()
    file_type = request.args.get('file_type', 'excel').lower()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    all_companies = []
    page = 1

    # Step 1: Fetch all pages of companies
    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            all_companies.extend(data['items'])
            if len(data['items']) < LIMIT:  # End of pagination
                break
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Step 2: Fetch company details in parallel
    detailed_companies = []
    with ThreadPoolExecutor(max_workers=10) as executor:  # Use 10 threads
        futures = {
            executor.submit(fetch_company_details, company.get("company_number")): company
            for company in all_companies if company.get("company_number")
        }

        for future in as_completed(futures):
            try:
                details = future.result()
                if details:
                    detailed_companies.append(details)
            except Exception as e:
                print(f"Error fetching details: {e}")

    # Step 3: Export to file
    if detailed_companies:
        filename = f"{query}_companies.{file_type}"
        filepath = export_to_file(detailed_companies, filename, file_type)
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        return jsonify({"error": "No company details found to export"}), 404



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

""" search companies per page 20 done"""

"""neeed to search all fields like sic,overdue accounts etc----"""