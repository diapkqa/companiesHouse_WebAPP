import json
import csv
import io
import hashlib
import os
from flask import Flask, request, jsonify, send_file
from openpyxl import Workbook
import requests

app = Flask(__name__)

# Configuration
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 10  # Results per page

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_file(query, page):
    """Generate a cache file path based on query and page."""
    cache_key = hashlib.md5(f"{query}-{page}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def fetch_companies_by_api(query, page=1):
    """Fetch companies from the Companies House API with pagination."""
    start_index = (page - 1) * LIMIT
    search_url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}&items_per_page={LIMIT}"

    cache_file = get_cache_file(query, page)

    # Check if cached data exists
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)

    # Fetch data from API
    response = requests.get(search_url, auth=(API_KEY, ""))
    if response.status_code == 200:
        data = response.json().get('items', [])
        with open(cache_file, 'w') as f:
            json.dump(data, f)
        return data

    return []


@app.route('/search', methods=['GET'])
def search_companies():
    """Search companies by a given term."""
    search_term = request.args.get("search_term")
    page = int(request.args.get("page", 1))

    if not search_term:
        return jsonify({"error": "Search term is required"}), 400

    companies = fetch_companies_by_api(search_term, page)

    if not companies:
        return jsonify({"error": "No companies found"}), 404

    return jsonify({"results": companies, "current_page": page, "search_term": search_term})


@app.route('/export', methods=['POST'])
def export_data():
    """Export company data to CSV or Excel."""
    data = request.get_json()
    file_type = data.get("file_type")
    search_term = data.get("search_term")

    if not search_term or file_type not in ["csv", "excel"]:
        return jsonify({"error": "Invalid data or file type"}), 400

    companies = []
    page = 1

    while True:
        fetched_companies = fetch_companies_by_api(search_term, page)
        if not fetched_companies:
            break
        companies.extend(fetched_companies)
        page += 1

    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

    return create_export_file(companies, file_type, search_term)


def create_export_file(companies, file_type, search_term):
    """Create export file (CSV or Excel)."""
    if file_type == "csv":
        return create_csv_export(companies, search_term)
    elif file_type == "excel":
        return create_excel_export(companies, search_term)


def create_csv_export(companies, search_term):
    """Create a CSV export file."""
    output = io.StringIO()
    fieldnames = list(companies[0].keys()) if companies else []
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for company in companies:
        writer.writerow(company)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{search_term}_companies.csv"
    )


def create_excel_export(companies, search_term):
    """Create an Excel export file."""
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(list(companies[0].keys()))
    for company in companies:
        ws.append(list(company.values()))
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"{search_term}_companies.xlsx"
    )


if __name__ == "__main__":
    app.run(debug=True)
