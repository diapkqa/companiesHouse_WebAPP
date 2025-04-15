import os
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Global variable to store companies in cache memory
all_companies = []

@app.route('/api/export', methods=['GET'])
def export_companies_to_excel():
    if not all_companies:
        return jsonify({"error": "No data available to export. Please fetch companies first."}), 400

    company_rows = []
    for company in all_companies:
        try:
            company_rows.append({
                "Company Name": company.get("companyInfo", {}).get("companyName", "N/A"),
                "Company Number": company.get("companyInfo", {}).get("companyNumber", "N/A"),
                "Registered Office Address": company.get("companyDetails", {}).get("RegisteredOfficeAddress", "N/A"),
                "Company Type": company.get("companyDetails", {}).get("CompanyType", "N/A"),
                "Company Status": company.get("companyDetails", {}).get("CompanyStatus", "N/A"),
                "Incorporated Date": company.get("companyDetails", {}).get("IncorporatedDate", "N/A"),
                "Accounts Next Statement Date": company.get("accounts", {}).get("AccountsNextStatementDate", "N/A"),
                "Accounts Due Date": company.get("accounts", {}).get("AccountsDueDate", "N/A"),
                "Accounts Last Statement Date": company.get("accounts", {}).get("AccountsLastStatementDate", "N/A"),
                "Confirmation Next Statement Date": company.get("confirmationStatement", {}).get("ConfirmationNextStatementDate", "N/A"),
                "Confirmation Due Date": company.get("confirmationStatement", {}).get("ConfirmationDueDate", "N/A"),
                "Confirmation Last Statement Date": company.get("confirmationStatement", {}).get("ConfirmationLastStatementDate", "N/A"),
                "Nature of Business": ", ".join([
                    f"{entry.get('sicCode', 'N/A')}: {entry.get('Description', 'N/A')}"
                    for entry in company.get("natureOfBusiness", [])
                ]),
                "Previous Company Names": ", ".join([
                    f"{name.get('name', 'N/A')} (Start: {name.get('startPrevNameDate', 'N/A')}, End: {name.get('endPrevNameDate', 'N/A')})"
                    for name in company.get("previousCompanyNames", [])
                ]),
            })
        except Exception as e:
            print(f"Error processing company data: {e}")

    if not company_rows:
        return jsonify({"error": "No valid company details to export"}), 500

    df = pd.DataFrame(company_rows)

    # Save to Excel
    export_file_path = os.path.join("exported_companies.xlsx")
    try:
        df.to_excel(export_file_path, index=False, engine='openpyxl')
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        return jsonify({"error": "Failed to save Excel file"}), 500

    return send_file(export_file_path, as_attachment=True, download_name="exported_companies.xlsx")

@app.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    page_param = request.args.get('page', '1').strip()  # Get page parameter as string

    # Validate page parameter
    if not page_param.isdigit():
        return jsonify({"error": "Invalid page number"}), 400

    page = int(page_param)

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    data = fetch_companies(query, page)
    if data and 'items' in data:
        # Fetch detailed information for each company
        detailed_companies = []
        for company in data['items']:
            company_number = company.get("company_number")
            if company_number:
                company_details = fetch_company_details(company_number)
                detailed_companies.append(company_details)

        # Store the fetched companies in the cache memory
        all_companies.extend(detailed_companies)

        # Get total number of results and total pages from the API response
        total_results = data.get('total_results', len(detailed_companies))  # Fallback if field is missing
        total_pages = (total_results // LIMIT) + (1 if total_results % LIMIT else 0)

        return jsonify({
            "message": "Companies fetched successfully...",
            "data": detailed_companies,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_results": total_results
            }
        })
    else:
        return jsonify({"error": "No companies found"}), 404

if __name__ == '__main__':
    app.run(host='192.168.16.104', port=5000, debug=True)
    # app.run(host='192.168.1.120', port=5000, debug=True)