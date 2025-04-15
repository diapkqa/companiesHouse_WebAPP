from flask import Flask, request, render_template, send_file, jsonify
import requests
import csv
import io
from openpyxl import Workbook

app = Flask(__name__)

API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"

def fetch_companies_by_search(query, start=0, limit=10):
    """Fetch companies from the Companies House API with pagination."""
    search_url = f"{BASE_URL}/search/companies?q={query}&start_index={start}&items_per_page={limit}"
    response = requests.get(search_url, auth=(API_KEY, ""))
    if response.status_code == 200:
        return response.json()
    return None

def extract_company_data(company):
    """Extract relevant fields from the company data for export."""
    return {
        "Company Name": company.get("title", "N/A"),
        "Company Number": company.get("company_number", "N/A"),
        "Registered Office Address": company.get("registered_office_address", {}).get("address_line_1", "N/A"),
        "Company Status": company.get("company_status", "N/A"),
        "Company Type": company.get("company_type", "N/A"),
        "Incorporated On": company.get("date_of_creation", "N/A"),
        "Accounts Overdue": company.get("accounts", {}).get("overdue", "No"),
        "Confirmation Statement Overdue": company.get("confirmation_statement", {}).get("overdue", "No"),
        "Nature of Business (SIC)": ", ".join(company.get("sic_codes", []))
    }

@app.route('/search', methods=['GET', 'POST'])
def search_companies():
    """Handles company search and renders the search page."""
    if request.method == 'POST':
        search_term = request.form.get("search_term")
        if not search_term:
            return render_template("index.html", error="Search term is required", results=None)

        query = search_term
        companies = []
        start = 0
        limit = 10  # Fetch only 10 companies per page to avoid performance issues

        while True:
            data = fetch_companies_by_search(query, start, limit)
            if data and data.get('items'):
                for company in data['items']:
                    # Filter companies based on the search query matching name or number
                    if query.lower() in company.get("title", "").lower() or query.lower() in company.get("company_number", "").lower():
                        companies.append({
                            "Company Name": company.get("title", "N/A"),
                            "Company Number": company.get("company_number", "N/A")
                        })
                if len(data['items']) < limit:
                    break
                start += limit  # Move to the next page of results
            else:
                break

        if not companies:
            return render_template("index-three.html", error="No Company Found", results=None)

        return render_template("index-three.html", results=companies, search_term=search_term)

    return render_template("index-three.html", results=None)

@app.route('/export', methods=['POST'])
def export_data():
    """Exports company data as CSV or Excel."""
    file_type = request.args.get("file_type")
    search_term = request.args.get("search_term")

    if not search_term or file_type not in ["csv", "excel"]:
        return jsonify({"error": "Invalid data or file type"}), 400

    companies = []
    start = 0
    limit = 10

    # Fetch all pages of companies based on the search term for export
    while True:
        data = fetch_companies_by_search(search_term, start, limit)
        if data and data.get('items'):
            for company in data['items']:
                company_data = extract_company_data(company)
                companies.append(company_data)
            if len(data['items']) < limit:
                break
            start += limit
        else:
            break

    # If no companies found during export, return error message
    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Export the data
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
            download_name="companies.csv"
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
            download_name="companies.xlsx"
        )


if __name__ == "__main__":
    app.run(debug=True)
