import asyncio
import aiohttp
import json

# Replace with your actual Companies House API key
API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"


async def search_companies_by_name(session, company_name, items_per_page=50):
    """
    Search for companies by name with pagination using Companies House API.

    :param session: The aiohttp session object.
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

        # Fetch the search results with a GET request
        async with session.get(url, params=params, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
            if response.status == 200:
                result = await response.json()
                companies = result.get("items", [])
                all_companies.extend(companies)

                # If the number of companies returned is less than the items per page, we've reached the last page.
                if len(companies) < items_per_page:
                    break

                # Otherwise, move to the next page.
                start_index += items_per_page
            else:
                print(f"Failed to search companies by name. HTTP Status Code: {response.status}")
                break

    return all_companies


async def extract_company_details(session, company_number):
    """
    Fetch the full details of a company by its company number.

    :param session: The aiohttp session object.
    :param company_number: The unique company number.
    :return: Detailed company information.
    """
    url = f"{BASE_URL}/company/{company_number}"
    async with session.get(url, auth=aiohttp.BasicAuth(API_KEY, "")) as response:
        if response.status == 200:
            return await response.json()
        else:
            print(f"Failed to fetch company details for number {company_number}. HTTP Status Code: {response.status}")
            return None


async def main():
    company_name = "UKPA"  # Replace with the company name you are searching for

    async with aiohttp.ClientSession() as session:
        # Step 1: Get the list of companies using pagination
        print(f"Searching for companies named '{company_name}'...\n")
        companies = await search_companies_by_name(session, company_name)

        if not companies:
            print("No companies found.")
        else:
            print(f"\nTotal companies found: {len(companies)}")
            print("Fetching details for each company...\n")

            # Step 2: Fetch details for each company concurrently
            tasks = []
            for company in companies:
                company_name = company["title"]
                company_number = company["company_number"]
                print(f"Fetching details for {company_name} ({company_number})...")

                # Create a task to fetch details asynchronously
                task = extract_company_details(session, company_number)
                tasks.append(task)

            # Run all the tasks concurrently
            company_details = await asyncio.gather(*tasks)

            # Step 3: Process or print the company details
            for details in company_details:
                if details:
                    print(f"\nCompany Name: {details.get('company_name', 'N/A')}")
                    print(f"Company Number: {details.get('company_number', 'N/A')}")
                    print(f"Registered Office Address: {details.get('registered_office_address', 'N/A')}")
                    print(f"Company Status: {details.get('company_status', 'N/A')}")
                    print(f"Company Type: {details.get('company_type', 'N/A')}")
                    print(f"Incorporated On: {details.get('date_of_creation', 'N/A')}")
                    print(f"SIC Codes: {', '.join(details.get('sic_codes', []))}")
                    print("\n---\n")
                else:
                    print(f"Failed to fetch details for a company.\n")


# Start the asynchronous event loop
if __name__ == "__main__":
    asyncio.run(main())
