from flask import Blueprint, request, jsonify, send_file
import pandas as pd
import os
from .search_by_name import fetch_companies  # Import the fetch function

export_companies = Blueprint('export_companies', __name__)

CACHE_DIR = './cache'

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

@export_companies.route('/', methods=['GET'])
def export_companies_data():
    """Export all searched companies to an Excel file."""
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Search term is required"}), 400

    page = 1
    all_companies = []

    while True:
        data = fetch_companies(query, page)
        if data and 'items' in data:
            all_companies.extend(data['items'])
            if len(data['items']) < 20:  # Adjust for the results per page
                break
            page += 1
        else:
            break

    if not all_companies:
        return jsonify({"error": "No companies found to export"}), 404

    # Convert list of company data to DataFrame
    df = pd.DataFrame(all_companies)
    file_path = os.path.join(CACHE_DIR, "exported_companies.xlsx")
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)
