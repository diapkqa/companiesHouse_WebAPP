from flask import Flask, request, render_template, send_file, jsonify
import csv
import io
from openpyxl import Workbook
import requests
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Constants
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"  # Replace with your actual API key
BASE_URL = "https://api.company-information.service.gov.uk"

# Helper function to fetch company data
def fetch_companies_by_api(query, page=1, limit=10):
    """Fetch companies from the Companies House API with pagination."""
    start_index = (page - 1) * limit
    search_url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}&items_per_page={limit}"

    logging.debug(f"Fetching page {page} with start_index {start_index} and limit {limit}")
    response = requests.get(search_url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json().get('items', [])

    logging.error(f"Error fetching data: {response.status_code} - {response.text}")
    return []

# Helper function to extract relevant company data
def extract_company_data(company):
    """Extract relevant fields from the company data for export."""
    return {
        "Company Name": company.get("title", "N/A"),
        "Company Number": company.get("company_number", "N/A"),
        "Registered Office Address": company.get("registered_office_address", {}).get("address_line_1", "N/A"),
        "Company Status": company.get("company_status", "N/A"),
        "Company Type": company.get("company_type", "N/A"),
        "Incorporated On": company.get("date_of_creation", "N/A"),
        "Nature of Business (SIC)": ", ".join(company.get("sic_codes", []))
    }

# Route to search companies
@app.route('/search', methods=['GET', 'POST'])
def search_companies():
    if request.method == 'POST':
        search_term = request.form.get("search_term")
        page = 1
    else:
        search_term = request.args.get("search_term")
        page = int(request.args.get("page", 1))

    if not search_term:
        return render_template("index-8.html", error="Search term is required", results=None)

    limit = 20
    companies = fetch_companies_by_api(search_term, page, limit)

    if not companies:
        return render_template(
            "index-8.html",
            error="No companies found.",
            results=None,
            search_term=search_term,
            current_page=page
        )

    results = [extract_company_data(company) for company in companies]

    return render_template(
        "index-8.html",
        results=results,
        search_term=search_term,
        current_page=page
    )

# Route to export company data
@app.route('/export', methods=['POST'])
def export_data():
    """Exports all company data for a search term across all pages."""
    try:
        data = request.get_json()
        file_type = data.get("file_type")  # Either 'csv' or 'excel'
        search_term = data.get("search_term")
    except Exception:
        return jsonify({"error": "Invalid JSON payload."}), 400

    if not search_term or file_type not in ["csv", "excel"]:
        return jsonify({"error": "Invalid data or file type."}), 400

    # Accumulate all company data from all pages
    companies = []
    page = 1
    limit = 10

    while True:
        data = fetch_companies_by_api(search_term, page, limit)
        if data:
            companies.extend([extract_company_data(company) for company in data])
            page += 1
        else:
            break

    if not companies:
        return jsonify({"error": "No companies found to export."}), 404

    # Generate CSV or Excel
    if file_type == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=companies[0].keys())
        writer.writeheader()
        writer.writerows(companies)
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{search_term}_companies.csv"
        )
    elif file_type == "excel":
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

# Main entry point
if __name__ == "__main__":
    app.run(debug=True)
