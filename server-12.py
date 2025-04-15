import os
import hashlib
import json
import csv
import io
from flask import Flask, request, jsonify, send_file
import requests
from openpyxl import Workbook

app = Flask(__name__)

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

def extract_company_details(company_number):
    """Extract detailed company data."""
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))
    if response.status_code == 200:
        return response.json()
    return {}

def create_csv(companies):
    """Generate CSV file from company data."""
    output = io.StringIO()
    fieldnames = companies[0].keys() if companies else []
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(companies)
    output.seek(0)
    return output

def create_excel(companies):
    """Generate Excel file from company data."""
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(list(companies[0].keys()) if companies else [])
    for company in companies:
        ws.append(list(company.values()))
    wb.save(output)
    output.seek(0)
    return output

@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    search_type = request.args.get('type', 'name').strip().lower()
    page = int(request.args.get('page', 1))

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Determine API endpoint based on search type
    if search_type == "number":
        # Directly fetch the company details by company number
        url = f"{BASE_URL}/company/{query}"
        response = requests.get(url, auth=(API_KEY, ""))
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Company not found"}), 404

    elif search_type == "sic":
        # Fetch all companies, filtering by SIC code
        url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={(page - 1) * LIMIT}"
        response = requests.get(url, auth=(API_KEY, ""))
        if response.status_code == 200:
            data = response.json()
            # Filter results for companies matching the SIC code
            companies = [
                item for item in data.get('items', [])
                if query in item.get('sic_codes', [])
            ]
            if companies:
                return jsonify(companies)
            else:
                return jsonify({"error": "No companies found with the specified SIC code"}), 404
        else:
            return jsonify({"error": "Failed to fetch data"}), response.status_code

    else:  # Default to name search
        url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={(page - 1) * LIMIT}"
        response = requests.get(url, auth=(API_KEY, ""))
        if response.status_code == 200:
            data = response.json()
            return jsonify(data.get('items', []))
        else:
            return jsonify({"error": "Failed to fetch data"}), response.status_code

@app.route('/api/export', methods=['POST'])
def export_companies():
    """Export company data to CSV or Excel."""
    data = request.json
    query = data.get('query')
    file_type = data.get('file_type')
    search_type = data.get('type', 'name').strip().lower()

    if not query or file_type not in ['csv', 'excel']:
        return jsonify({"error": "Invalid request"}), 400

    companies = []
    page = 1
    while True:
        data = fetch_companies(query, page)
        if not data or 'items' not in data or not data['items']:
            break
        companies.extend(data['items'])
        page += 1

    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

    if file_type == 'csv':
        output = create_csv(companies)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{query}_companies.csv"
        )
    elif file_type == 'excel':
        output = create_excel(companies)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{query}_companies.xlsx"
        )

if __name__ == '__main__':
    app.run(debug=True)
