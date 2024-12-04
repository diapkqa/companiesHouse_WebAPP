import asyncio
import aiohttp
from flask import Flask, request, jsonify, send_file
import pandas as pd
import io
import json

# Flask app initialization
app = Flask(__name__)

# Replace with your actual Companies House API key
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"


# Function to search companies by name, number, or SIC code
async def search_companies(session, search_term, search_type="name", items_per_page=50):
    all_companies = []
    start_index = 0

    while True:
        url = f"{BASE_URL}/search/companies"
        params = {"q": search_term, "items_per_page": items_per_page, "start_index": start_index}

        if search_type == "number":
            params = {"q": f"company_number:{search_term}"}
        elif search_type == "sic":
            params = {"q": f"sic_code:{search_term}"}

        async with session.get(url, params=params, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
            if response.status == 200:
                result = await response.json()
                companies = result.get("items", [])
                all_companies.extend(companies)

                if len(companies) < items_per_page:
                    break
                start_index += items_per_page
            else:
                break
    return all_companies


# Function to get detailed company data
async def get_company_details(session, company_number):
    url = f"{BASE_URL}/company/{company_number}"
    async with session.get(url, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
        if response.status == 200:
            return await response.json()
        return None


# API endpoint to search companies and return results
@app.route('/search', methods=['GET'])
async def search_companies_api():
    search_term = request.args.get('search_term')
    search_type = request.args.get('search_type', 'name')
    async with aiohttp.ClientSession() as session:
        companies = await search_companies(session, search_term, search_type)

        if not companies:
            return jsonify({"message": "No companies found."}), 404

        company_details = []
        tasks = []
        for company in companies:
            company_number = company["company_number"]
            task = get_company_details(session, company_number)
            tasks.append(task)

        company_details = await asyncio.gather(*tasks)

        # Transform company details into a format suitable for export (list of dictionaries)
        formatted_details = []
        for details in company_details:
            if details:
                formatted_details.append({
                    "Company Name": details.get("company_name", ""),
                    "Company Number": details.get("company_number", ""),
                    "Status": details.get("company_status", ""),
                    "Type": details.get("company_type", ""),
                    "Address": details.get("registered_office_address", ""),
                    "Incorporation Date": details.get("date_of_creation", ""),
                    "SIC Codes": ", ".join(details.get("sic_codes", [])),
                })

        return jsonify(formatted_details)


# Export the search results to CSV or Excel
@app.route('/export', methods=['POST'])
def export_to_file():
    data = request.json
    file_type = request.args.get('file_type', 'csv')

    if file_type == 'csv':
        df = pd.DataFrame(data)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name="companies.csv")

    elif file_type == 'excel':
        df = pd.DataFrame(data)
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name="companies.xlsx")

    return jsonify({"message": "Invalid file type."}), 400


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
