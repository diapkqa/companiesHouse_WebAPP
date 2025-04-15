from flask import Flask
from flask_cors import CORS

# Import the routes
from api.search_by_name import search_companies_by_name
from api.search_by_number import search_companies_by_number
from api.search_by_sic import search_companies_by_sic
from api.export_companies import export_companies

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Register the routes
app.register_blueprint(search_companies_by_name, url_prefix='/api/search-by-name')
app.register_blueprint(search_companies_by_number, url_prefix='/api/search-by-number')
app.register_blueprint(search_companies_by_sic, url_prefix='/api/search-by-sic')
app.register_blueprint(export_companies, url_prefix='/api/export')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
