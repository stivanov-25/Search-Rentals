import requests
import json
import os
import time
from dotenv import load_dotenv


# load environment variables
load_dotenv()

# Output files
CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "cache")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "output")

# filter
MINUMUM_PRICE = 1400
MAXIMUM_PRICE = 2800

# openrouteservice
OPENROUTESERVICE_RPM_LIMIT = 30;
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY")

# work coordinates
WORK_LAT = os.getenv("WORK_LAT")
WORK_LON = os.getenv("WORK_LON")

# daft API headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.daft.ie/",
    "X-Requested-With": "XMLHttpRequest"
}

def get_daft_location(city, page = 1):
    properties = []
    listings_travel_time = {}
    parameters = [
        f"rentalPrice_from={MINUMUM_PRICE}",
        f"rentalPrice_to={MAXIMUM_PRICE}",
        "sort=publishDateDesc",
        "pageSize=20",
        f"from={(page - 1) * 20}"
    ]

    url = f"https://www.daft.ie/property-for-rent/{city}?{'&'.join(parameters)}"
    print(f"URL: {url}")

    try:
        response = requests.get(url, headers=headers)
        html = response.text
        
        json_str = html.split('<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">')[1].split('</script>')[0]
        json_data = json.loads(json_str)

        for listing in json_data['props']['pageProps']['listings']:
            processed_listing, travel_time = process_listing(listing['listing'])
            if processed_listing is not None:
                properties.append(processed_listing)
                listings_travel_time[processed_listing['seoFriendlyPath']] = travel_time
        
        # Recursively get next page if we got full page of results
        if len(json_data['props']['pageProps']['listings']) == 20 and page <= 10:
            next_page_properties = get_daft_location(city, page + 1)
            properties.extend(next_page_properties)
            
        # Cache results on first page
        if page == 1:
            os.makedirs(CACHE_FOLDER, exist_ok=True)
            with open(f"{CACHE_FOLDER}/{city}.json", "w") as f:
                json.dump({"properties": properties}, f, indent=2)
            with open(f"{CACHE_FOLDER}/{city}_travel_time.json", "w") as f:
                json.dump(listings_travel_time, f, indent=2)
                
        return properties
        
    except Exception as e:
        print(f"Error fetching properties: {str(e)}")
        return []
    

def process_listing(listing):
    if 'seoFriendlyPath' not in listing:
        return None, None
    
    if 'propertyType' not in listing or listing['propertyType'].lower() == 'studio':
        return None, None
    
    if listing['propertyType'] == 'Apartment':
        if 'numBedrooms' not in listing or listing['numBedrooms'].lower() != "1 bed":
            return None, None
        else:
            # Exclude properties that are too far away from the office
            publicTravelTime = get_travel_time_to_work(listing, 40)
            if publicTravelTime is None:
                return None, None
            return listing, publicTravelTime
    
    if listing['propertyType'] != 'Apartments':
        return None, None

    url = f"https://www.daft.ie{listing['seoFriendlyPath']}"

    try:
        response = requests.get(url, headers=headers)
        html = response.text
        
        # Extract JSON data from the Next.js script tag
        json_str = html.split('<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">')[1].split('</script>')[0]
        json_data = json.loads(json_str)
        
        for listing in json_data['props']['pageProps']['listings']:
            processed_listing = process_listing(listing['listing'])
            if processed_listing is not None:
                # Exclude properties that are too far away from the office
                publicTravelTime = get_travel_time_to_work(processed_listing, 30)
                if publicTravelTime is None:
                    return None, None
                return listing, publicTravelTime
            
        return None, None
        
    except Exception as e:
        print(f"Error fetching listing: {str(e)}")
        return None, None
    

def get_travel_time_to_work(property, limit):
    # Exclude properties that are too far away from the office
    if 'point' not in property or 'coordinates' not in property['point']:
        return None
    
    [lng, lat] = property['point']['coordinates']
    publicTravelTime = get_travel_time("driving-car", property['seoFriendlyPath'], lat, lng)
    if publicTravelTime is None:
        print(f"Could not compute travel time for {property['seoFriendlyPath']}.")
        return None
    
    if publicTravelTime > limit * 60:
        print(f"Property {property['seoFriendlyPath']} is too far away from the office. Travel time: {publicTravelTime} seconds.")
        return None
    
    return publicTravelTime
    

def get_travel_time(transportType, id, lat, lng):
    url = f"https://api.openrouteservice.org/v2/directions/{transportType}?api_key={OPENROUTESERVICE_API_KEY}&start={lng},{lat}&end={WORK_LON},{WORK_LAT}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if 'features' in data:
            summary = data['features'][0]['properties']['summary']
            duration = summary['duration']
            # Rate limit API calls
            time.sleep(60 / OPENROUTESERVICE_RPM_LIMIT)
            return duration
            
    except Exception as e:
        print(f"Error getting distance for property {id}: {str(e)}")
        return None