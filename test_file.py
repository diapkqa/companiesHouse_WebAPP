import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

API_URL = "https://find-and-update.company-information.service.gov.uk/advanced-search/get-results"
API_KEY = '03ed5851-da50-4a59-9c87-d903055fd3e6'  # Replace with your Companies House API key

@app.route('/search', methods=['GET'])
def search_companies_SIC():
    sic_code = request.args.get('sic_code')
    page = request.args.get('page', default=1, type=int)

    if not sic_code:
        return jsonify({"error": "SIC code is required"}), 400

    params = {
        'sicCodes': sic_code,
        'itemsPerPage': 20,  # Limit to 20 results per page
        'startIndex': (page - 1) * 20,
    }

    # Make the request to the Companies House API
    response = requests.get(API_URL, params=params, auth=(API_KEY, ''))

    # Debugging: Print status code, content type, and response text for debugging
    print(f"Status Code: {response.status_code}")
    print(f"Response Content-Type: {response.headers.get('Content-Type')}")
    print(f"Response Content: {response.text}")  # Print raw response text

    # Check if the response is valid JSON
    if response.status_code == 200:
        try:
            data = response.json()  # Attempt to decode JSON
            companies = data.get('items', [])
            total_results = data.get('totalResults', 0)
            total_pages = (total_results // 20) + (1 if total_results % 20 > 0 else 0)

            return jsonify({
                "companies": companies,
                "total_results": total_results,
                "total_pages": total_pages,
                "current_page": page
            })
        except ValueError as e:
            print(f"Error decoding JSON: {e}")
            return jsonify({"error": "Failed to parse JSON response from Companies House API"}), 500
    else:
        # Log the error status and raw content for debugging
        print(f"Error status code: {response.status_code}")
        print(f"Error response content: {response.text}")
        return jsonify({"error": f"Failed to fetch data from Companies House API, Status Code: {response.status_code}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
