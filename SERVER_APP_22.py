import os
import hashlib
import json
import requests
import pandas as pd
import asyncio
import aiohttp
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"  # Replace with your API Key
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
    start_index = (page - 1) * LIMIT  # Start index based on LIMIT
    url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}&items_per_page={LIMIT}"
    print(f"Fetching Page {page}: {url}")  # Debug: Print the query URL

    cache_file = get_cache_file(query, page)

    # Check cache first
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    # Fetch from API
    response = requests.get(url, auth=(API_KEY, ""))
    print(f"Status Code: {response.status_code}")  # Debug: Print status code
    if response.status_code == 200:
        data = response.json()
        print(f"Fetched {len(data.get('items', []))} companies")  # Debug: Number of companies returned
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        return data
    else:
        print(f"API Error: {response.text}")  # Debug: Print error response
        return None


async def fetch_company_details_async(session, company_number):
    """Asynchronous function to fetch company details."""
    url = f"{BASE_URL}/company/{company_number}"
    async with session.get(url, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
        if response.status == 200:
            data = await response.json()
            return {
                "CompanyName": data.get("company_name", "N/A"),
                "CompanyNumber": data.get("company_number", "N/A"),
                "IncorporatedDate": data.get("date_of_creation", "N/A"),
                "CompanyStatus": data.get("company_status", "N/A"),
                "CompanyType": data.get("type", "N/A"),
                "RegisteredAddress": data.get("registered_office_address", {}).get("address_line_1", "N/A"),
                "SICCodes": ", ".join(data.get("sic_codes", [])) if "sic_codes" in data else "N/A"
            }
        else:
            return None


async def fetch_all_details_async(company_numbers):
    """Fetch details for all companies concurrently."""
    tasks = []
    async with aiohttp.ClientSession() as session:
        for company_number in company_numbers:
            tasks.append(fetch_company_details_async(session, company_number))
        results = await asyncio.gather(*tasks)
    return [result for result in results if result is not None]


@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', 1))  # Page number from request

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch companies for the requested page
    data = fetch_companies(query, page)
    if data and 'items' in data:
        companies = data['items']
        return jsonify(companies)
    else:
        return jsonify({"error": "No companies found"}), 404


@app.route('/api/export', methods=['GET'])
def export_companies():
    """Export searched companies to an Excel or CSV file."""
    query = request.args.get('query', '').strip()
    file_type = request.args.get('file_type', 'excel').lower()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Step 1: Fetch all pages of companies
    all_companies = []
    page = 1
    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            all_companies.extend(data['items'])
            if len(data['items']) < LIMIT:
                break  # Stop if fewer results are returned
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found"}), 404

    # Step 2: Extract company numbers
    company_numbers = [company.get("company_number") for company in all_companies if company.get("company_number")]

    # Step 3: Fetch company details asynchronously
    print("Fetching company details asynchronously...")
    company_details = asyncio.run(fetch_all_details_async(company_numbers))

    if not company_details:
        return jsonify({"error": "No detailed company information found to export"}), 404

    # Step 4: Export data to Excel or CSV
    df = pd.DataFrame(company_details)
    filename = f"{query}_companies.{file_type}"
    filepath = os.path.join(CACHE_DIR, filename)

    if file_type == 'excel':
        df.to_excel(filepath, index=False)
    elif file_type == 'csv':
        df.to_csv(filepath, index=False)

    return send_file(filepath, as_attachment=True, download_name=filename)


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
