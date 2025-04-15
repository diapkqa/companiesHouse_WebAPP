import requests
import hashlib
import os
import json

API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"

def fetch_companies(search_param):
    url = f"{BASE_URL}/search/companies?{search_param}&items_per_page=10000"
    response = requests.get(url, auth=(API_KEY, ""))
    if response.status_code == 200:
        return response.json()
    return None

def fetch_company_details(company_number):
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))
    if response.status_code == 200:
        return response.json()
    return None
