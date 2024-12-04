import requests

API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"


def fetch_company_data(company_number):
    """
    Fetch company details from Companies House API.

    :param company_number: The unique company number to query.
    :return: JSON response from the API or None if the request fails.
    """
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))  # Auth requires username (API key) and blank password.

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch company details. HTTP Status Code: {response.status_code}")
        print(response.text)  # Debug information for API error
        return None


def format_payload(company_data):
    """
    Format company data into the required JSON structure for the frontend.

    :param company_data: JSON data retrieved from Companies House API.
    :return: Formatted JSON payload.
    """
    payload = {
        "companyInfo": {
            "companyName": company_data.get("company_name", "N/A"),
            "companyNumber": company_data.get("company_number", "N/A"),
        },
        "companyDetails": {
            "RegisteredOfficeAddress": ", ".join(filter(None, [
                company_data.get("registered_office_address", {}).get("address_line_1"),
                company_data.get("registered_office_address", {}).get("address_line_2"),
                company_data.get("registered_office_address", {}).get("locality"),
                company_data.get("registered_office_address", {}).get("region"),
                company_data.get("registered_office_address", {}).get("postal_code")
            ])),
            "CompanyType": company_data.get("type", "N/A"),
            "CompanyStatus": company_data.get("company_status", "N/A"),
            "IncorporatedDate": company_data.get("date_of_creation", "N/A"),
        },
        "accounts": {
            "AccountsNextStatementDate": company_data.get("accounts", {}).get("next_due", "N/A"),
            "AccountsDueDate": company_data.get("accounts", {}).get("next_made_up_to", "N/A"),
            "AccountsLastStatementDate": company_data.get("accounts", {}).get("last_accounts", {}).get("made_up_to",
                                                                                                       "N/A"),
        },
        "confirmationStatement": {
            "ConfirmationNextStatementDate": company_data.get("confirmation_statement", {}).get("next_due", "N/A"),
            "ConfirmationDueDate": company_data.get("confirmation_statement", {}).get("next_made_up_to", "N/A"),
            "ConfirmationLastStatementDate": company_data.get("confirmation_statement", {}).get("last_made_up_to",
                                                                                                "N/A"),
        },
        "natureOfBusiness": {
            "siCode": ", ".join(company_data.get("sic_codes", [])),
            "Description": "N/A"  # Replace with actual descriptions if available or map SIC codes to descriptions.
        },
        "previousCompanyNames": [
            {
                "name": name.get("name", "N/A"),
                "startPrevNameDate": name.get("effective_from", "N/A"),
                "endPrevNameDate": name.get("ceased_on", "N/A"),
            }
            for name in company_data.get("previous_company_names", [])
        ],
    }
    return payload


# Example usage
if __name__ == "__main__":
    company_number = "12345678"  # Replace with the actual company number
    company_data = fetch_company_data(company_number)

    if company_data:
        payload = format_payload(company_data)
        print(payload)  # Provide this JSON to the frontend developer
