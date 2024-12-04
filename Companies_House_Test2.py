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
        print(f"Failed to search companies. HTTP Status Code: {response.status_code}")
        print(response.text)  # Debug information for API error
        return []


def fetch_company_overview(company_number):
    """
    Fetch detailed overview of a company using its company number.

    :param company_number: Unique company number for the company.
    :return: JSON response with detailed overview or None if request fails.
    """
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch company overview for {company_number}. HTTP Status Code: {response.status_code}")
        print(response.text)  # Debug information for API error
        return None


def extract_payload_from_overview(company_data):
    """

    Format the overview data into a structured JSON payload.

    :param company_data: Raw data from the company overview API.
    :return: Formatted JSON payload.
    """
    payload = {
        "companyName": company_data.get("company_name", "N/A"),
        "companyNumber": company_data.get("company_number", "N/A"),
        "RegisteredOfficeAddress": ", ".join(filter(None, [
            company_data.get("registered_office_address", {}).get("address_line_1"),
            company_data.get("registered_office_address", {}).get("address_line_2"),
            company_data.get("registered_office_address", {}).get("locality"),
            company_data.get("registered_office_address", {}).get("postal_code"),
        ])),
        "CompanyType": company_data.get("type", "N/A"),
        "CompanyStatus": company_data.get("company_status", "N/A"),
        "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        "Accounts": {
            "NextDueDate": company_data.get("accounts", {}).get("next_due", "N/A"),
            "LastMadeUpDate": company_data.get("accounts", {}).get("last_accounts", {}).get("made_up_to", "N/A"),
        },
        "ConfirmationStatement": {
            "NextDueDate": company_data.get("confirmation_statement", {}).get("next_due", "N/A"),
            "LastMadeUpDate": company_data.get("confirmation_statement", {}).get("last_made_up_to", "N/A"),
        },
        "SICCodes": ", ".join(company_data.get("sic_codes", [])),
        "PreviousCompanyNames": [
            {
                "Name": name.get("name", "N/A"),
                "StartDate": name.get("effective_from", "N/A"),
                "EndDate": name.get("ceased_on", "N/A"),
            }
            for name in company_data.get("previous_company_names", [])
        ],
    }
    return payload


def main():
    # Part 1: Search for companies by name
    company_name = "UKPA"  # Replace with the company name keyword
    companies = search_companies_by_name(company_name)

    if not companies:
        print("No companies found.")
        return

    print("Matching companies found:")
    for company in companies:
        print(f" - {company['company_name']} ({company['company_number']})")

    # Part 2: Extract and print overview data for each company
    print("\nFetching detailed data for each company:")
    for company in companies:
        print(f"\nFetching data for {company['company_name']} ({company['company_number']})...")
        overview_data = fetch_company_overview(company["company_number"])
        if overview_data:
            payload = extract_payload_from_overview(overview_data)
            print(payload)  # Provide this JSON to the frontend developer


if __name__ == "__main__":
    main()
