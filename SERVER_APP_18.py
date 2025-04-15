import os
import hashlib
import json
import asyncio
import aiohttp
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
MAX_WORKERS = 10  # Number of parallel threads for API requests
RETRY_DELAY = 30  # Delay in seconds when rate limit (429) is encountered

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


async def fetch_companies_async(session, query, page=1):
    """Asynchronous function to fetch companies with caching."""
    url = f"{BASE_URL}/search/companies"
    params = {"q": query, "start_index": (page - 1) * 20, "items_per_page": 20}
    cache_file = get_cache_file(query, page)

    # Use cache if available
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    try:
        async with session.get(url, params=params, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
            if response.status == 200:
                data = await response.json()
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
                return data
            elif response.status == 429:
                print(f"Rate limit reached. Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
                return await fetch_companies_async(session, query, page)  # Retry the same request
            else:
                print(f"Error fetching page {page}: {response.status}")
    except Exception as e:
        print(f"Exception during API call: {str(e)}")

    return None


async def fetch_all_companies_async(query):
    """Fetch all companies for the given query across all pages asynchronously."""
    all_companies = []
    page = 1

    async with aiohttp.ClientSession() as session:
        while True:
            print(f"Fetching page {page}...")
            data = await fetch_companies_async(session, query, page)
            if not data or 'items' not in data or len(data['items']) == 0:
                print(f"No more data on page {page}.")
                break

            # Add the companies from this page to the list
            all_companies.extend(data['items'])

            # Check if there is a next page
            if 'links' in data and 'next' not in data['links']:
                print(f"Last page {page} reached.")
                break

            # Increase the page number to fetch the next page
            page += 1

    print(f"Total companies fetched: {len(all_companies)}")
    return all_companies


async def fetch_company_details_parallel_async(company_numbers):
    """Asynchronously fetch company details in parallel."""
    async def fetch_details(session, company_number):
        url = f"{BASE_URL}/company/{company_number}"
        try:
            async with session.get(url, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    print(f"Rate limit reached for company {company_number}. Retrying...")
                    await asyncio.sleep(RETRY_DELAY)
                    return await fetch_details(session, company_number)  # Retry the same request
                return {"company_number": company_number, "error": f"Failed with status {response.status}"}
        except Exception as e:
            return {"company_number": company_number, "error": str(e)}

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_details(session, num) for num in company_numbers]
        return await asyncio.gather(*tasks)


def export_to_excel(companies, filename):
    """Export company details to an Excel file."""
    df = pd.DataFrame(companies)
    filepath = os.path.join(CACHE_DIR, filename)
    df.to_excel(filepath, index=False)
    return filepath


@app.route('/api/search', methods=['GET'])
async def search_companies():
    """Search companies by name or number."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies (basic info) across all pages asynchronously
    companies = await fetch_all_companies_async(query)
    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Fetch detailed company info in parallel asynchronously
    print("Fetching detailed information for all companies...")
    company_numbers = [c.get("company_number") for c in companies if c.get("company_number")]
    detailed_companies = await fetch_company_details_parallel_async(company_numbers)

    return jsonify(detailed_companies)


@app.route('/api/export', methods=['GET'])
async def export_companies():
    """Export companies to an Excel file."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Fetch all companies asynchronously
    companies = await fetch_all_companies_async(query)
    if not companies:
        return jsonify({"error": "No companies found"}), 404

    # Fetch detailed info asynchronously
    print("Fetching detailed information for all companies...")
    company_numbers = [c.get("company_number") for c in companies if c.get("company_number")]
    detailed_companies = await fetch_company_details_parallel_async(company_numbers)

    if detailed_companies:
        filename = f"{query}_companies.xlsx"
        filepath = export_to_excel(detailed_companies, filename)
        return send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return jsonify({"error": "No company details found to export"}), 404


if __name__ == '__main__':
    app.run(host='192.168.1.87', port=5000, debug=True)
