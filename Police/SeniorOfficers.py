import requests
from textwrap import fill

def get_all_forces():
    """Get list of all police forces from the API"""
    url = "https://data.police.uk/api/forces"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching forces: {response.status_code}")
        return []

def format_bio(bio):
    """Format the bio text for better display"""
    if not bio:
        return "No bio available"
    # Remove HTML tags and clean up text
    clean_bio = bio.replace("<p>", "").replace("</p>", "\n\n").replace("<br />", "\n")
    clean_bio = clean_bio.replace("\n\n", "\n").strip()
    return fill(clean_bio, width=80)  # Wrap text to 80 characters

def display_people_data(force_name, people_data):
    """Display the people data in a nicely formatted way"""
    print(f"\n{'=' * 80}")
    print(f"PEOPLE IN {force_name.upper()} POLICE FORCE")
    print(f"{'=' * 80}\n")
    
    for person in people_data:
        print(f"{'─' * 40}")
        print(f"NAME: {person['name']}")
        print(f"RANK: {person['rank']}")
        print("\nBIO:")
        print(format_bio(person.get('bio')))
        
        # Display contact details if available
        if person.get('contact_details'):
            print("\nCONTACT DETAILS:")
            for key, value in person['contact_details'].items():
                print(f"- {key.title()}: {value}")
        
        print(f"{'─' * 40}\n")

def check_people_endpoints(forces):
    """Check each force's /people endpoint and display nicely formatted results"""
    found_data = False
    
    for force in forces:
        force_id = force['id']
        force_name = force['name']
        url = f"https://data.police.uk/api/forces/{force_id}/people"
        response = requests.get(url)
        
        if response.status_code == 200:
            people_data = response.json()
            if people_data:
                found_data = True
                display_people_data(force_name, people_data)
    
    if not found_data:
        print("\nNo police forces returned people data.")

def main():
    print("Fetching list of all police forces...")
    forces = get_all_forces()
    
    if forces:
        print(f"\nChecking /people endpoints for {len(forces)} forces...")
        check_people_endpoints(forces)
    else:
        print("No forces found to check.")

if __name__ == "__main__":
    main()