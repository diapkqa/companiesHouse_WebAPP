from flask import Blueprint, request, jsonify
import requests

search_companies_by_sic = Blueprint('search_companies_by_sic', __name__)

BASE_URL = "https://api.company-information.service.gov.uk"
API_KEY = "your_api_key_here"
LIMIT = 20  # Results per page

def fetch_companies(query, page=1):
    start_index = (page - 1) * LIMIT
    url = f"{BASE_URL}/search/companies?q={query}&items_per_page={LIMIT}&start_index={start_index}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json()
    return None

@search_companies_by_sic.route('/', methods=['GET'])
def search_by_sic():
    query = request.args.get('query', '').strip()
    page = int(request.args.get('page', '1').strip())

    if not query:
        return jsonify({"error": "SIC code is required"}), 400

    try:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            return jsonify({"message": "Companies fetched successfully...", "data": data['items']}), 200
        else:
            return jsonify({"error": "No companies found"}), 404
    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500
