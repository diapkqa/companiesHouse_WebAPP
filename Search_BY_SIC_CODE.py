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


"""---Search Companies---"""


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API by company name."""
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
#Advance search

#https://api.company-information.service.gov.uk/advanced-search/companies

#sic_codes	list
#The SIC codes advanced search filter. To search using multiple values, use a comma delimited list or multiple of the same key i.e. sic_codes=xxx&sic_codes=yyy

"""----Search Companies BY SIC CODE----"""


def fetch_companies_by_sic(sic_codes, page=1):
    start_index = (page - 1) * LIMIT
    url = f"https://api.company-information.service.gov.uk/search/companies?q={sic_codes}&items_per_page={LIMIT}&start_index={start_index}"

    print(f"Request URL: {url}")

    response = requests.get(url, auth=(API_KEY, ""))
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            data = response.json()
            print(f"API Response Data: {json.dumps(data, indent=2)}")  # Pretty print the response
            total_results = data.get("total_results", 0)
            if total_results == 0:
                print(f"No companies found for SIC code {sic_codes} on page {page}")
                return None
            elif total_results > 0:
                # You may want to loop through pages if you expect more results
                print(f"Found {total_results} companies for SIC code {sic_codes}")
                return data
        except ValueError as e:
            print(f"Error parsing JSON: {e}")
            return None
    else:
        print(f"Error fetching data: {response.status_code} - {response.text}")
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
        }
        if "accounts" in company_data:
            accounts_data = company_data["accounts"]
            accounts["AccountsNextStatementDate"] = accounts_data.get("next_accounts", "N/A")
            accounts["AccountsDueDate"] = accounts_data.get("next_due", "N/A")
            accounts["AccountsLastStatementDate"] = accounts_data.get("last_accounts", "N/A")

        # Fetch confirmation statement information
        confirmation_statement = {
            "ConfirmationNextStatementDate": "N/A",
            "ConfirmationDueDate": "N/A",
            "ConfirmationLastStatementDate": "N/A"
        }
        if "confirmation_statement" in company_data:
            confirmation_statement_data = company_data["confirmation_statement"]
            confirmation_statement["ConfirmationNextStatementDate"] = confirmation_statement_data.get("next_made_up_to",
                                                                                                      "N/A")
            confirmation_statement["ConfirmationDueDate"] = confirmation_statement_data.get("next_due", "N/A")
            confirmation_statement["ConfirmationLastStatementDate"] = confirmation_statement_data.get("last_made_up_to",
                                                                                                      "N/A")

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
    """Search companies by company number, name, or SIC code."""
    company_number = request.args.get('companyNumber', '').strip()
    company_name = request.args.get('companyName', '').strip()
    sic_code = request.args.get('sicCode', '').strip()
    page = int(request.args.get('page', 1))

    # Validate that at least one parameter is provided
    if not (company_number or company_name or sic_code):
        return jsonify(
            {"error": "At least one search parameter (companyNumber, companyName, sicCode) is required."}), 400

    # If company number is provided, fetch details for that company
    if company_number:
        company_details = fetch_company_details(company_number)
        if company_details:
            return jsonify({"message": "Company fetched successfully.", "data": company_details})
        else:
            return jsonify({"error": "No company found with the provided number."}), 404

    # If company name is provided, search using company name
    if company_name:
        data = fetch_companies(company_name, page)
        if data and 'items' in data:
            detailed_companies = []
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    company_details = fetch_company_details(company_number)
                    detailed_companies.append(company_details)

            if detailed_companies:
                return jsonify({
                    "message": "Companies fetched successfully.",
                    "data": detailed_companies
                })
            else:
                return jsonify({"error": "No detailed company information found"}), 404
        else:
            return jsonify({"error": "No companies found for the given company name."}), 404

    # If SIC code is provided, search using SIC code
    if sic_code:
        data = fetch_companies_by_sic(sic_code, page)
        if data and 'items' in data:
            detailed_companies = []
            for company in data['items']:
                company_number = company.get("company_number")
                if company_number:
                    company_details = fetch_company_details(company_number)
                    detailed_companies.append(company_details)

            if detailed_companies:
                return jsonify({
                    "message": "Companies fetched successfully.",
                    "data": detailed_companies
                })
            else:
                return jsonify({"error": "No detailed company information found"}), 404
        else:
            return jsonify({"error": "No companies found for the given SIC code."}), 404


if __name__ == '__main__':
    app.run(host='192.168.1.65', port=5000, debug=True)





