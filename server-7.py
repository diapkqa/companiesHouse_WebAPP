from flask import Flask, request, render_template, send_file, jsonify
import requests
import csv
import io
from openpyxl import Workbook

app = Flask(__name__)

API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"


def fetch_companies_by_search(query, page=1, limit=10):
    """Fetch companies from the Companies House API with pagination."""
    start_index = (page - 1) * limit
    search_url = f"{BASE_URL}/search/companies?q={query}&start_index={start_index}&items_per_page={limit}"

    print(f"Fetching page {page} with start_index {start_index} and limit {limit}")
    response = requests.get(search_url, auth=(API_KEY, ""))

    if response.status_code == 200:
        print(f"Response for page {page}: {response.json()}")
        return response.json()

    print(f"Error: {response.status_code} - {response.text}")
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
        "Accounts": company.get("Next_accounts_made_up_to", {}).get("due_by",{}).get("last_accounts_made_up_to"),
        "Confirmation_Statement": company.get("next_statement_date",{}).get("due_by",{}).get("last_statement_dated"),
        "Accounts Overdue": company.get("Next_accounts_made_up_to", {}).get("overdue", "No",{}).get("due by",{}).get("Last accounts made up to",{}),
        "Confirmation Statement Overdue": company.get("confirmation_statement_overdue", {}).get("Next statement date",{}).get("due_by",{}).get("last_statement_dated"),
        "Nature of Business (SIC)": ", ".join(company.get("sic_codes", []))
    }


@app.route('/search', methods=['GET', 'POST'])
def search_companies():
    if request.method == 'POST':
        search_term = request.form.get("search_term")
        page = 1
    else:
        search_term = request.args.get("search_term")
        page = int(request.args.get("page", 1))

    if not search_term:
        return render_template("index-five.html", error="Search term is required", results=None)

    limit = 20
    data = fetch_companies_by_search(search_term, page, limit)
    companies = []

    if data and data.get('items'):
        for company in data['items']:
            companies.append({
                "Company Name": company.get("title", "N/A"),
                "Company Number": company.get("company_number", "N/A")
            })
    else:
        print(f"No results found for page {page}")

    if not companies:
        return render_template(
            "index-4.html",
            error="No companies found",
            results=None,
            search_term=search_term,
            current_page=page
        )

    return render_template(
        "index-4.html",
        results=companies,
        search_term=search_term,
        current_page=page
    )
@app.route('/export', methods=['GET'])
def export_data():
    """Exports all company data for a search term across all pages."""
    file_type = request.args.get("file_type")  # Either 'csv' or 'excel'
    search_term = request.args.get("search_term")

    if not search_term or file_type not in ["csv", "excel"]:
        return jsonify({"error": "Invalid data or file type"}), 400

    # Accumulate all company data from all pages
    companies = []
    page = 1
    limit = 10

    while True:
        data = fetch_companies_by_search(search_term, page, limit)
        if data and data.get('items'):
            for company in data['items']:
                companies.append(extract_company_data(company))
            page += 1
        else:
            break

    if not companies:
        return jsonify({"error": "No companies found to export"}), 404

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


if __name__ == "__main__":
    app.run(debug=True)
