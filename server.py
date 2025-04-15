from flask import Flask, jsonify, request, send_file,redirect,url_for,render_template
from flask_cors import CORS
import requests
import csv
import io

app = Flask(__name__)
CORS(app)

API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"

def fetch_companies_by_search(query, search_type="company_name", start_index=0):
    """
    Fetch companies by search query (company name, company number, or SIC code) with pagination.
    """
    search_url = f"{BASE_URL}/search/companies?q={query}&start={start_index}&items_per_page=50"
    response = requests.get(search_url, auth=(API_KEY, ""))
    # print(response.json()) #for test

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch companies. HTTP Status Code: {response.status_code}")
        return render_template('frontend.html')


def fetch_company_data(company_number):
    """
    Fetch company details by company number from Companies House API.
    """
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))
    # print(response.json()) #For Testing

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch company details. HTTP Status Code: {response.status_code}")
        return render_template('frontend.html')


def format_payload(company_data):
    payload = {
        "companyInfo": {
            "companyName": company_data.get("company_name", "N/A"),
            "companyNumber": company_data.get("company_number", "N/A"),
        },
        "companyDetails": {
            "RegisteredOfficeAddress": ", ".join(filter(None, [
                company_data.get("registered_office_address", {}).get("address_line_1"),
                company_data.get("registered_office_address", {}).get("address_line_2"),
                company_data.get("registered_office_address", {}).get("locality"),
                company_data.get("registered_office_address", {}).get("region"),
                company_data.get("registered_office_address", {}).get("postal_code")
            ])),
            "CompanyType": company_data.get("type", "N/A"),
            "CompanyStatus": company_data.get("company_status", "N/A"),
            "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        },
        "accounts": {
            "AccountsNextStatementDate": company_data.get("accounts", {}).get("next_due", "N/A"),
            "AccountsDueDate": company_data.get("accounts", {}).get("next_made_up_to", "N/A"),
            "AccountsLastStatementDate": company_data.get("accounts", {}).get("last_accounts", {}).get("made_up_to",
                                                                                                       "N/A"),
        },
        "confirmationStatement": {
            "ConfirmationNextStatementDate": company_data.get("confirmation_statement", {}).get("next_due", "N/A"),
            "ConfirmationDueDate": company_data.get("confirmation_statement", {}).get("next_made_up_to", "N/A"),
            "ConfirmationLastStatementDate": company_data.get("confirmation_statement", {}).get("last_made_up_to",
                                                                                                "N/A"),
        },
        "natureOfBusiness": {
            "siCode": ", ".join(company_data.get("sic_codes", [])),
            "Description": "N/A"
        },
        "previousCompanyNames": [
            {
                "name": name.get("name", "N/A"),
                "startPrevNameDate": name.get("effective_from", "N/A"),
                "endPrevNameDate": name.get("ceased_on", "N/A"),
            }
            for name in company_data.get("previous_company_names", [])
        ],
    }
    return payload


@app.route('/home', methods=['GET'])
def homePage():
    return render_template('frontend.html')


@app.route('/search', methods=['GET'])
def search_companies():
    query = request.args.get('query')
    search_type = request.args.get('search_type', 'company_name')

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    all_companies = []
    start_index = 0

    while True:
        data = fetch_companies_by_search(query, search_type, start_index)

        if data and data.get('items'):
            companies = data.get('items')
            for company in companies:
                company_data = fetch_company_data(company['company_number'])
                if company_data:
                    formatted_data = format_payload(company_data)
                    all_companies.append(formatted_data)

            if len(companies) < 50:
                break
            else:
                start_index += 50
        else:
            break

    return jsonify(all_companies)
    return render_template('frontend.html')


@app.route('/export', methods=['GET'])
def export_to_csv():
    companies_data = request.args.getlist('companies_data')

    if not companies_data:
        return jsonify({"error": "No company data to export"}), 400

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["companyName", "companyNumber", "RegisteredOfficeAddress",
                                                "CompanyType", "CompanyStatus", "IncorporatedDate",
                                                "AccountsNextStatementDate", "AccountsDueDate",
                                                "AccountsLastStatementDate", "ConfirmationNextStatementDate",
                                                "ConfirmationDueDate", "ConfirmationLastStatementDate",
                                                "NatureOfBusiness", "PreviousCompanyNames"])
    writer.writeheader()

    for company in companies_data:
        writer.writerow({
            "companyName": company.get("companyInfo", {}).get("companyName"),
            "companyNumber": company.get("companyInfo", {}).get("companyNumber"),
            "RegisteredOfficeAddress": company.get("companyDetails", {}).get("RegisteredOfficeAddress"),
            "CompanyType": company.get("companyDetails", {}).get("CompanyType"),
            "CompanyStatus": company.get("companyDetails", {}).get("CompanyStatus"),
            "IncorporatedDate": company.get("companyDetails", {}).get("IncorporatedDate"),
            "AccountsNextStatementDate": company.get("accounts", {}).get("AccountsNextStatementDate"),
            "AccountsDueDate": company.get("accounts", {}).get("AccountsDueDate"),
            "AccountsLastStatementDate": company.get("accounts", {}).get("AccountsLastStatementDate"),
            "ConfirmationNextStatementDate": company.get("confirmationStatement", {}).get(
                "ConfirmationNextStatementDate"),
            "ConfirmationDueDate": company.get("confirmationStatement", {}).get("ConfirmationDueDate"),
            "ConfirmationLastStatementDate": company.get("confirmationStatement", {}).get(
                "ConfirmationLastStatementDate"),
            "NatureOfBusiness": company.get("natureOfBusiness", {}).get("Description"),
            "PreviousCompanyNames": ", ".join([name['name'] for name in company.get("previousCompanyNames", [])])
        })

    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="companies_data.csv")


if __name__ == "__main__":
    app.run(debug=True)
