import requests
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def make_api_request():
    url = "https://discovery.nationalarchives.gov.uk/API/search/records"
    params = {
        'query': 'Cathars',
        'digitised': 'true',
        'page': '1',
        'pageSize': '1'
    }
    
    headers = {
        'Accept': 'application/json'
    }
    
    logging.info(f"Making request to: {url}")
    logging.info(f"Request parameters: {params}")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        logging.info(f"Request URL: {response.url}")
        logging.info(f"Status Code: {response.status_code}")
        logging.info(f"Response URL: {response.url}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logging.info(f"Received response: {data}")
             

            except requests.exceptions.JSONDecodeError:
                logging.error("Failed to decode JSON response")
                logging.debug(f"Response text: {response.text}")
        else:
            logging.error(f"API request failed with status code {response.status_code}")
            logging.debug(f"Response text: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    make_api_request()