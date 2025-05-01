import requests
import logging
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def make_api_request(query_term):
    # Base URL
    base_url = "https://discovery.nationalarchives.gov.uk/API/search/records"
    
    # Parameters for the request
    params = {
        'query': query_term,
        'digitised': 'true',
        'page': '1',
        'pageSize': '1'
    }
    
    # Headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Log request details
    logging.info(f"Making request to: {base_url}")
    logging.info(f"Request parameters: {params}")
    
    try:
        # Make the GET request
        response = requests.get(base_url, params=params, headers=headers)
        
        # Log response details
        logging.info(f"Request URL: {response.url}")
        logging.info(f"Status Code: {response.status_code}")
        logging.info(f"Response URL: {response.url}")
        
        # Check for successful response
        if response.status_code == 200:
            try:
                # Try to parse JSON response
                data = response.json()
                logging.info(f"Received response: {data}")
                
                # Log total results
                total_results = data.get('totalResults', 0)
                logging.info(f"Total results: {total_results}")
                
                if total_results > 0:
                    # Return first result
                    return data['results'][0]
                else:
                    logging.warning("No results found in response")
                    return None
            except requests.exceptions.JSONDecodeError:
                logging.error("Failed to decode JSON response")
                logging.info(f"Raw response content: {response.text}")
                return None
        else:
            logging.error(f"API request failed with status code {response.status_code}")
            logging.info(f"Response content: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        return None

if __name__ == "__main__":
    # Test with a known query term
    result = make_api_request("Cathars")
    
    if result:
        print("\nFound resource:")
        print(f"Title: {result.get('title', 'N/A')}")
        print(f"Reference: {result.get('reference', 'N/A')}")
        print(f"Description: {result.get('description', 'N/A')}")
        print(f"Date range: {result.get('coveringDates', 'N/A')}")
    else:
        print("\nNo resource found.")