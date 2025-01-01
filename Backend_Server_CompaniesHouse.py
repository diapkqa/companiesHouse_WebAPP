import os
import hashlib

import threading
from concurrent.futures import ThreadPoolExecutor

# Thread-safe list to store all company details
lock = threading.Lock()
all_companies = []
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file,render_template,redirect
from flask_cors import CORS
app = Flask(__name__)
CORS(app)

"""""""----Configuration---"""


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


"""---Search Companies---"""

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


#---- Old Code without implementation search by SIC--------

@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    page_param = request.args.get('page', '1').strip()  # Get page parameter as string

    # Validate page parameter
    if not page_param.isdigit():
        return jsonify({"error": "Invalid page number"}), 400

    page = int(page_param)

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
            # return jsonify(detailed_companies)
            return jsonify({
                "message": "Companies fetched successfully...",
                "data": detailed_companies
            })
        else:
            return jsonify({"error": "No detailed company information found"}), 404
    else:
        return jsonify({"error": "No companies found"}), 404








"""#EXPORT TO EXCEL OR CSV FILE"""





def fetch_and_store_company_details(company_number):
    """Fetch company details and store them in the shared list."""
    try:
        details = fetch_company_details(company_number)
        with lock:
            all_companies.append(details)
    except Exception as e:
        print(f"Error fetching details for company number {company_number}: {e}")


@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    """Export all searched companies to an Excel file with optimisations."""
    query = request.args.get('query', '').strip()
    page = 1
    all_companies.clear()  # Clear shared list before export

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    company_numbers = []

    # Fetch all company numbers
    while True:
        try:
            data = fetch_companies(query, page)
            if data and 'items' in data:
                company_numbers.extend([
                    company.get("company_number")
                    for company in data['items']
                    if company.get("company_number")
                ])
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

    # Fetch details in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(fetch_and_store_company_details, company_numbers)

    # Convert to DataFrame
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
                "Nature of Business": ", ".join([
                    f"{entry.get('sicCode', 'N/A')}: {entry.get('Description', 'N/A')}"
                    for entry in company.get("natureOfBusiness", [])
                ]),
                "Previous Company Names": ", ".join([
                    f"{name.get('name', 'N/A')} (Start: {name.get('startPrevNameDate', 'N/A')}, End: {name.get('endPrevNameDate', 'N/A')})"
                    for name in company.get("previousCompanyNames", [])
                ]),
            })
        except Exception as e:
            print(f"Error processing company data: {e}")

    if not company_rows:
        return jsonify({"error": "No valid company details to export"}), 500

    df = pd.DataFrame(company_rows)

    # Save to Excel
    export_file_path = os.path.join(CACHE_DIR, f"{query}_companies.xlsx")
    try:
        df.to_excel(export_file_path, index=False, engine='openpyxl')
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        return jsonify({"error": "Failed to save Excel file"}), 500

    return send_file(export_file_path, as_attachment=True, download_name=f"{query}_companies.xlsx")




@app.route('/api/search-and-export', methods=['GET'])
def search_and_export():
    """Perform a search and export all results to Excel."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    return export_companies_to_excel()




"""___UPLOAD EXCEL/CSV File"""

@app.route('/api/upload', methods=['POST'])
def upload_and_display_companies():
    """Handle file upload and display company details."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    try:
        df = pd.read_excel(file)
        if 'company_number' not in df.columns:
            return jsonify({"error": "The uploaded file must contain a 'company_number' column."}), 400

        company_numbers = df['company_number'].dropna().astype(str).tolist()

        # Paginate results
        page_param = request.args.get('page', '1').strip()
        if not page_param.isdigit():
            return jsonify({"error": "Invalid page number"}), 400
        page = int(page_param)

        start_index = (page - 1) * LIMIT
        end_index = start_index + LIMIT

        # Fetch company details for the current page
        detailed_companies = []
        for company_number in company_numbers[start_index:end_index]:
            company_details = fetch_company_details(company_number)
            if company_details:
                detailed_companies.append(company_details)

        if not detailed_companies:
            return jsonify({"error": "No companies found for the provided numbers or page."}), 404



        return jsonify({
            "message": "File uploaded and companies fetched successfully.",
            "data": detailed_companies
        })

    except Exception as e:
        return jsonify({"error": f"Error processing the file: {str(e)}"}), 500




if __name__ == '__main__':
    app.run(host='192.168.1.119',port=5000,debug=True)






