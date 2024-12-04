import requests

# Companies House API key
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"  # Replace with your actual Companies House API key
BASE_URL = "https://api.company-information.service.gov.uk"

def search_companies_by_name(company_name):
    """
    Search for companies by name using Companies House API.

    :param company_name: The keyword to search for in company names.
    :return: List of matching companies with their basic information.
    """
    url = f"{BASE_URL}/search/companies"
    params = {"q": company_name}
    response = requests.get(url, params=params, auth=(API_KEY, ""))

    if response.status_code == 200:
        companies = response.json().get("items", [])
        return [
            {"company_name": company["title"], "company_number": company["company_number"]}
            for company in companies
        ]
    else:
        print(f"Failed to search companies by name. HTTP Status Code: {response.status_code}")
        print(response.text)
        return []


def search_company_by_number(company_number):
    """
    Search for a company by its company number.

    :param company_number: The unique company number.
    :return: Company details in JSON format.
    """
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch company details for number {company_number}. HTTP Status Code: {response.status_code}")
        print(response.text)
        return None


def search_companies_by_sic_code(sic_code):
    """
    Search for companies by SIC code.

    :param sic_code: The SIC code (Standard Industry Classification).
    :return: List of matching companies with their basic information.
    """
    url = f"{BASE_URL}/search/companies"
    params = {"q": sic_code}
    response = requests.get(url, params=params, auth=(API_KEY, ""))

    if response.status_code == 200:
        companies = response.json().get("items", [])
        return [
            {"company_name": company["title"], "company_number": company["company_number"]}
            for company in companies
        ]
    else:
        print(f"Failed to search companies by SIC code. HTTP Status Code: {response.status_code}")
        print(response.text)
        return []


def main():
    # Part 1: Search for companies by name
    company_name = "UKPA"  # Replace with the company name keyword
    companies_by_name = search_companies_by_name(company_name)

    if not companies_by_name:
        print("No companies found by name.")
    else:
        print("\nCompanies found by name:")
        for company in companies_by_name:
            print(f" - {company['company_name']} ({company['company_number']})")

    # Part 2: Search for a company by number
    company_number = "05872127"  # Replace with the actual company number
    company_details = search_company_by_number(company_number)

    if company_details:
        print("\nCompany details by number:")
        print(company_details)  # This will display detailed information

    # Part 3: Search for companies by SIC code
    sic_code = "82990"  # Replace with the actual SIC code
    companies_by_sic = search_companies_by_sic_code(sic_code)

    if not companies_by_sic:
        print("No companies found by SIC code.")
    else:
        print("\nCompanies found by SIC code:")
        for company in companies_by_sic:
            print(f" - {company['company_name']} ({company['company_number']})")


if __name__ == "__main__":
    main()
