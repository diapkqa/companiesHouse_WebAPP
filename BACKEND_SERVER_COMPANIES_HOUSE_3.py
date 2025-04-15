"""---Import Dependencies---"""
import os
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
lock = threading.Lock()
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS


"""---"Configuration---"""
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 20  # Number of results per page
os.makedirs(CACHE_DIR, exist_ok=True)
lock = threading.Lock()
all_companies = []

app = Flask(__name__)
CORS(app)



"""---ForCache Handling---"""


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")





"""---Required Fields to Fetch---"""

def fetch_company_details(company_number):
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

        return {
            "companyInfo": company_info,
            "companyDetails": company_details,
            "accounts": accounts,
            "confirmationStatement": confirmation_statement,
            "natureOfBusiness": nature_of_business,
            "previousCompanyNames": previous_names,
        }

    return {}


# def fetch_companies(query, page=1):
#     start_index = (page - 1) * LIMIT
#     url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"
#     response = requests.get(url, auth=(API_KEY, ""))
#
#     if response.status_code == 200:
#         return response.json()
#     return None




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




@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name or SIC code."""
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', '1').strip())

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    try:
        data = fetch_companies(query, page)
        if data and 'items' in data:
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


"""#EXPORT By Name  TO EXCEL OR CSV FILE"""


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



#
# @app.route('/api/export', methods=['GET'])
# def export_companies_to_excel():
#     """Export all searched companies to an Excel file."""
#     query = request.args.get('query', '').strip()
#     if not query:
#         return jsonify({"error": "Search term is required"}), 400
#
#     page = 1
#     all_companies.clear()
#
#     while True:
#         data = fetch_companies(query, page)
#         if data and 'items' in data:
#             company_numbers = [company.get("company_number") for company in data['items'] if company.get("company_number")]
#             if not company_numbers:
#                 break
#
#             with ThreadPoolExecutor(max_workers=10) as executor:
#                 executor.map(fetch_company_details, company_numbers)
#
#
#             if len(data['items']) < LIMIT:
#                 break
#             page += 1
#         else:
#             break
#
#     if not all_companies:
#         return jsonify({"error": "No companies found to export"}), 404
#
#     df = pd.DataFrame(all_companies)
#     file_path = os.path.join(os.getcwd(), "exported_companies.xlsx")
#     df.to_excel(file_path, index=False)
#
#     return send_file(file_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='192.168.1.70', port=5000, debug=True)




from flask import Flask, request, jsonify, send_file
import requests
import pandas as pd
from io import BytesIO

app = Flask(__name__)

COMPANY_API_URL = "https://api.company-information.service.gov.uk/search/companies"


@app.route('/search', methods=['GET'])
def search_companies():
    sic_code = request.args.get('sic_code')
    page = int(request.args.get('page', 1))
    items_per_page = 20
    start_index = (page - 1) * items_per_page

    # Request to Companies House API with pagination
    response = requests.get(
        COMPANY_API_URL,
        params={
            'q': sic_code,
            'items_per_page': items_per_page,
            'start_index': start_index
        },
        auth=('your_api_key', '')  # Replace with your actual API key
    )

    data = response.json()
    companies = data.get('items', [])
    total_results = data.get('total_results', 0)
    total_pages = (total_results // items_per_page) + (1 if total_results % items_per_page else 0)

    return jsonify({
        'companies': companies,
        'total_results': total_results,
        'total_pages': total_pages,
        'current_page': page
    })


@app.route('/download', methods=['POST'])
def download():
    sic_code = request.json.get('sic_code')
    # Fetch all results from Companies House API
    all_companies = []
    page = 1
    while True:
        start_index = (page - 1) * 20
        response = requests.get(
            COMPANY_API_URL,
            params={
                'q': sic_code,
                'items_per_page': 20,
                'start_index': start_index
            },
            auth=('your_api_key', '')
        )
        data = response.json()
        companies = data.get('items', [])
        all_companies.extend(companies)

        # If fewer than 20 results, we reached the last page
        if len(companies) < 20:
            break
        page += 1

    # Create an Excel file from the list of companies
    df = pd.DataFrame(all_companies)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Companies')
    output.seek(0)

    # Send the file to the user for download
    return send_file(output, as_attachment=True, download_name="companies_list.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == '__main__':
    app.run(debug=True)















