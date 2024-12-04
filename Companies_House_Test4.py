import requests

# Companies House API key
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"  # Replace with your actual Companies House API key
BASE_URL = "https://api.company-information.service.gov.uk"

def search_companies_by_name(company_name, items_per_page=50):
    """
    Search for companies by name with pagination using Companies House API.

    :param company_name: The keyword to search for in company names.
    :param items_per_page: Number of results per page (max 50).
    :return: List of matching companies with their basic information.
    """
    all_companies = []
    start_index = 0

    while True:
        url = f"{BASE_URL}/search/companies"
        params = {
            "q": company_name,
            "items_per_page": items_per_page,
            "start_index": start_index
        }
        response = requests.get(url, params=params, auth=(API_KEY, ""))

        if response.status_code == 200:
            result = response.json()
            companies = result.get("items", [])
            all_companies.extend(companies)

            # If the number of companies returned is less than the items per page, we've reached the last page.
            if len(companies) < items_per_page:
                break

            # Otherwise, move to the next page.
            start_index += items_per_page
        else:
            print(f"Failed to search companies by name. HTTP Status Code: {response.status_code}")
            print(response.text)
            break

    return all_companies


def extract_company_details(company_number):
    """
    Fetch the full details of a company by its company number.

    :param company_number: The unique company number.
    :return: Detailed company information.
    """
    url = f"{BASE_URL}/company/{company_number}"
    response = requests.get(url, auth=(API_KEY, ""))

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch company details for number {company_number}. HTTP Status Code: {response.status_code}")
        print(response.text)
        return None


def main():
    company_name = "UKPA"  # Replace with the company name you are searching for
    companies = search_companies_by_name(company_name)

    if not companies:
        print("No companies found.")
    else:
        print(f"\nTotal companies found: {len(companies)}")
        print("Fetching details for each company...\n")

        # Loop through all companies and fetch their details
        for company in companies:
            company_name = company["title"]
            company_number = company["company_number"]
            print(f"Fetching details for {company_name} ({company_number})...")

            # Get detailed information for each company
            company_details = extract_company_details(company_number)

            if company_details:
                print(company_details)  # You can modify this to process or save the details
            print("\n---\n")


if __name__ == "__main__":
    main()
