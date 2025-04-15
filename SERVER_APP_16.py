import os
import hashlib
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
MAX_WORKERS = 10  # Number of parallel threads for API requests

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies(query, page=1):
    """Fetch companies from Companies House API with caching."""
    url = f"{BASE_URL}/search/companies"
    params = {"q": query, "start_index": (page - 1) * 20, "items_per_page": 20}
    cache_file = get_cache_file(query, page)

    # Use cache if available
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    # Fetch data from API
    try:
        response = requests.get(url, params=params, auth=(API_KEY, ""))
        if response.status_code == 200:
            data = response.json()
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            return data
        else:
            print(f"Error fetching page {page}: {response.status_code}")
    except Exception as e:
        print(f"Exception during API call: {str(e)}")

    return None


def fetch_all_companies(query):
    """Fetch all companies for the given query across all pages."""
    all_companies = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        data = fetch_companies(query, page)
        if not data or 'items' not in data or len(data['items']) == 0:
            print(f"No more data on page {page}.")
            break

        # Add the companies from this page to the list
        all_companies.extend(data['items'])

        # Check if there is a next page
        # If 'next' is in the response, continue fetching; otherwise, break
        if 'links' in data and 'next' not in data['links']:
            print(f"Last page {page} reached.")
            break

        # Increase the page number to fetch the next page
        page += 1

    print(f"Total companies fetched: {len(all_companies)}")
    return all_companies



def fetch_company_details_parallel(company_numbers):
    """Fetch company details in parallel using ThreadPoolExecutor."""
    results = []

    def fetch_details(company_number):
        url = f"{BASE_URL}/company/{company_number}"
        try:
            response = requests.get(url, auth=(API_KEY, ""))
            if response.status_code == 200:
                return response.json()
            return {"company_number": company_number, "error": f"Failed with status {response.status_code}"}
        except Exception as e:
            return {"company_number": company_number, "error": str(e)}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_details, num) for num in company_numbers]
        for future in as_completed(futures):
            results.append(future.result())

    return results


def export_to_excel(companies, filename):
    """Export company details to an Excel file."""
    df = pd.DataFrame(companies)
    filepath = os.path.join(CACHE_DIR, filename)
    df.to_excel(filepath, index=False)
    return filepath


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name or number."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies (basic info) across all pages
    companies = fetch_all_companies(query)
    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Fetch detailed company info in parallel
    print("Fetching detailed information for all companies...")
    company_numbers = [c.get("company_number") for c in companies if c.get("company_number")]
    detailed_companies = fetch_company_details_parallel(company_numbers)

    return jsonify(detailed_companies)


@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export companies to an Excel file."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies
    companies = fetch_all_companies(query)
    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Fetch detailed info in parallel
    print("Fetching detailed information for all companies...")
    company_numbers = [c.get("company_number") for c in companies if c.get("company_number")]
    detailed_companies = fetch_company_details_parallel(company_numbers)

    if detailed_companies:
        filename = f"{query}_companies.xlsx"
        filepath = export_to_excel(detailed_companies, filename)
        return send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return jsonify({"error": "No company details found to export"}), 404


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)

