import os
import hashlib
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 10  # Number of results per page
MAX_THREADS = 10  # Limit number of concurrent threads

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
    """Fetch all companies matching the query across all pages."""
    all_companies = []
    page = 1

    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            all_companies.extend(data['items'])
            if len(data['items']) < LIMIT:
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
        return response.json()
    return {}

def fetch_detailed_companies(all_companies):
    """Fetch detailed information for companies using multithreading."""
    detailed_companies = []

    def fetch_and_append(company):
        company_number = company.get("company_number")
        if company_number:
            details = fetch_company_details(company_number)
            if details:
                detailed_companies.append(details)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.map(fetch_and_append, all_companies)

    return detailed_companies

def format_company_for_export(company_data):
    """Format the company data into a structured format for easy Excel export."""
    company_info = company_data.get("company_name", "N/A")
    company_number = company_data.get("company_number", "N/A")
    company_status = company_data.get("company_status", "N/A")
    incorporation_date = company_data.get("date_of_creation", "N/A")

    # Extract SIC codes if available
    sic_codes = company_data.get("sic_codes", [])
    sic_code_str = ", ".join(sic_codes) if sic_codes else "N/A"

    # Registered office address
    registered_address = company_data.get("registered_office_address", {}).get("address_line_1", "N/A")

    # Nature of Business (SIC Codes with descriptions)
    nature_of_business = []
    if "sic_codes" in company_data and company_data["sic_codes"]:
        for sic_code in company_data["sic_codes"][:4]:  # Limit to 4 SIC codes
            nature_of_business.append({"sicCode": sic_code, "Description": "N/A"})  # Description placeholder
    else:
        nature_of_business.append({"sicCode": "N/A", "Description": "N/A"})  # Default entry if no SIC codes are available

    # Concatenate SIC codes and descriptions for easy reading in Excel
    sic_description_str = "; ".join([f"{entry['sicCode']} ({entry['Description']})" for entry in nature_of_business])

    return {
        "Company Name": company_info,
        "Company Number": company_number,
        "Company Status": company_status,
        "Incorporation Date": incorporation_date,
        "SIC Codes": sic_code_str,
        "Registered Office Address": registered_address,
        "Nature of Business (SIC Codes)": sic_description_str,  # Adding nature of business
    }

def export_to_excel(companies, filename):
    """Export company details to an Excel file with readable formatting."""
    formatted_companies = [format_company_for_export(company) for company in companies]
    df = pd.DataFrame(formatted_companies)
    filepath = os.path.join(CACHE_DIR, filename)
    df.to_excel(filepath, index=False)
    return filepath

@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', 1))

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    data = fetch_companies(query, page)
    if data and 'items' in data:
        return jsonify(data['items'])
    else:
        return jsonify({"error": "No companies found"}), 404

@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export all companies matching the query to an Excel file."""
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    all_companies = fetch_all_companies(query)
    detailed_companies = fetch_detailed_companies(all_companies)

    if detailed_companies:
        filename = f"{query}_companies.xlsx"
        filepath = export_to_excel(detailed_companies, filename)
        return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        return jsonify({"error": "No company details found to export"}), 404

if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
