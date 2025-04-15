from flask import Blueprint, request, jsonify
from utils.company_api import fetch_company_details
import pandas as pd

import_bp = Blueprint('import', __name__)

@import_bp.route('/api/import', methods=['POST'])
def import_companies():
    """Import companies from an Excel file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    df = pd.read_excel(file)

    detailed_companies = []
    for company_number in df['company_number']:
        details = fetch_company_details(company_number)
        detailed_companies.append(details)

    return jsonify(detailed_companies)
