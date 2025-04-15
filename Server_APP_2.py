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

def export_to_excel(companies, filename):
    """Export company details to an Excel file."""
    df = pd.DataFrame(companies)
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
    detailed_companies = []

    for company in all_companies:
        company_number = company.get("company_number")
        if company_number:
            company_details = fetch_company_details(company_number)
            detailed_companies.append(company_details)

    if detailed_companies:
        filename = f"{query}_companies.xlsx"
        filepath = export_to_excel(detailed_companies, filename)
        return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        return jsonify({"error": "No company details found to export"}), 404

if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
