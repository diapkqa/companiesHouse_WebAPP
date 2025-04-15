from flask import Blueprint, request, jsonify
from utils.company_api import fetch_company_details, fetch_companies

search_bp = Blueprint('search', __name__)

@search_bp.route('/api/search', methods=['GET'])
def search_companies():
    """Search companies by name, number, or SIC code."""
    query = request.args.get('query', '').strip()
    search_type = request.args.get('type', 'name').strip().lower()

    if not query:
        return jsonify({"error": "Search term is required"}), 400

    # Build the search parameter
    search_param = ''
    if search_type == 'name':
        search_param = f"q={query}"
    elif search_type == 'number':
        search_param = f"company_number={query}"
    elif search_type == 'sic':
        search_param = f"sic_codes={query}"
    else:
        return jsonify({"error": "Invalid search type. Use 'name', 'number', or 'sic'."}), 400

    # Fetch data
    data = fetch_companies(search_param)
    if data and 'items' in data:
        detailed_companies = []
        for company in data['items']:
            company_number = company.get("company_number")
            if company_number:
                company_details = fetch_company_details(company_number)
                detailed_companies.append(company_details)
        return jsonify(detailed_companies)
    else:
        return jsonify({"error": "No companies found"}), 404
