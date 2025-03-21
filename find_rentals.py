import sys
import requests
import json
import os
import time
from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI

# load environment variables
load_dotenv()

# Output files
CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "cache")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "output")

# filter
MINUMUM_PRICE = 1400
MAXIMUM_PRICE = 2800

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.daft.ie/",
    "X-Requested-With": "XMLHttpRequest"
}

# openrouteservice
OPENROUTESERVICE_RPM_LIMIT = 30;
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY")
publicTransportType = "public-transport"
walkingType = "foot-walking"

# work coordinates
WORK_LAT = os.getenv("WORK_LAT")
WORK_LON = os.getenv("WORK_LON")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

class PropertyRating(BaseModel):
    safetyRating: int
    gymRating: int
    restaurantsRating: int
    outdoorsRating: int


def get_daft_location(city, page = 1):
    properties = []
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
        
        # Extract JSON data from the Next.js script tag
        with open("html.txt", "w") as f:
            f.write(html)
        json_str = html.split('<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">')[1].split('</script>')[0]
        json_data = json.loads(json_str)

        for listing in json_data['props']['pageProps']['listings']:
            processed_listing = process_listing(listing['listing'])
            if processed_listing is not None:
                properties.append(processed_listing)
        
        # Recursively get next page if we got full page of results
        if len(json_data['props']['pageProps']['listings']) == 20 and page <= 15:
            time.sleep(0.05)
            next_page_properties = get_daft_location(city, page + 1)
            properties.extend(next_page_properties)
            
        # Cache results on first page
        if page == 1:
            os.makedirs(CACHE_FOLDER, exist_ok=True)
            with open(f"{CACHE_FOLDER}/{city}.json", "w") as f:
                json.dump({"properties": properties}, f, indent=2)
                
        return properties
        
    except Exception as e:
        print(f"Error fetching properties: {str(e)}")
        return []
    

def process_listing(listing):
    if 'seoFriendlyPath' not in listing:
        return None
    
    if 'propertyType' not in listing or listing['propertyType'].lower() == 'studio':
        return None
    
    if listing['propertyType'] == 'Apartment':
        if 'numBedrooms' not in listing or listing['numBedrooms'].lower() != "1 bed":
            return None
        else:
            # Exclude properties that are too far away from the office
            publicTravelTime = get_travel_time_to_work(listing, 30)
            if publicTravelTime is None:
                return None
            return listing
    
    if listing['propertyType'] != 'Apartments':
        return None

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
                    return None
                return listing
            
        return None
        
    except Exception as e:
        print(f"Error fetching listing: {str(e)}")
        return None
    
    
def extract_property_details(property):
    if ('price' not in property or 
        'ber' not in property or 
        'rating' not in property['ber'] or 
        'point' not in property or 
        'coordinates' not in property['point']):
        return None
    
    print(f"Processing property: {property['seoFriendlyPath']}")

    # Exclude properties that are too far away from the office
    publicTravelTime = get_travel_time_to_work(property, 30)
    if publicTravelTime is None:
        return None
    
    berRating = get_ber_rating(property['ber']['rating'])
    price = float(''.join(c for c in property['price'] if c.isdigit()))

    print(f"Asking OpenAI about property: {property['seoFriendlyPath']}. Travel time: {publicTravelTime} seconds.")
    [lng, lat] = property['point']['coordinates']
    propertyRating = generate_property_rating(lng, lat)

    print(f"Property: {property['seoFriendlyPath']}. Price: {price}. BER Rating: {berRating}. Public Travel Time: {publicTravelTime} seconds. Safety Rating: {propertyRating.safetyRating}. Gym Rating: {propertyRating.gymRating}. Restaurants Rating: {propertyRating.restaurantsRating}. Outdoors Rating: {propertyRating.outdoorsRating}.")

    return {
        "name": property['seoFriendlyPath'],
        "price": price,
        "berRating": berRating,
        "publicTravelTime": publicTravelTime,
        "safetyRating": propertyRating.safetyRating,
        "gymRating": propertyRating.gymRating,
        "restaurantsRating": propertyRating.restaurantsRating,
        "outdoorsRating": propertyRating.outdoorsRating,
    }


def generate_property_rating(lng, lat):
    systemPrompt = f"""
    You are a real estate agent.
    You are given a property and you need to rate it based on the following criteria:
    - Safety Rating (e.g. crime rate, safety of the area, etc.)
    - Rating on how close nearby gyms are
    - Restaurants and Cafes Rating
    - Outdoors Rating (e.g. parks, green spaces, etc.)
    """

    userPrompt = f"""
    The property is located at longitude {lng} and latitude {lat}). Please rate the property based on the criteria.
    """

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": userPrompt}
        ],
        response_format=PropertyRating,
    )

    if (completion.choices[0].message.refusal):
        return None
    
    return completion.choices[0].message.parsed


def get_travel_time_to_work(property, limit):
    # Exclude properties that are too far away from the office
    if 'point' not in property or 'coordinates' not in property['point']:
        return None
    
    [lng, lat] = property['point']['coordinates']
    publicTravelTime = get_travel_time("driving-car", property['seoFriendlyPath'], lat, lng)
    if publicTravelTime is None:
        print(f"Could not compute public travel time for {property['seoFriendlyPath']}.")
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

        
def rate_properties():
    with open(os.path.join(CACHE_FOLDER, "dublin.json"), "r") as f:
        properties = json.load(f)
        properties_with_ratings = []
        for property in properties['properties']:
            property_details = extract_property_details(property)
            if property_details is not None:
                properties_with_ratings.append(property_details)

        with open(os.path.join(OUTPUT_FOLDER, "dublin.json"), "w") as f:
            json.dump(properties_with_ratings, f, indent=2)


def score_property(property_details):
    distanceScore = distance_score(property_details['publicTravelTime'])
    ber_score = property_details['berRating']
    priceScore= price_score(property_details['price'])
    score = priceScore + ber_score + distanceScore + 25 * (property_details['safetyRating'] + property_details['gymRating'] + property_details['restaurantsRating'] + property_details['outdoorsRating'])
    return property_details['name'], score


def get_ber_rating(rating):
    # Return a score of -40 to 100
    scoring = 0
    if not rating or len(rating) < 1:
        return scoring
    
    if rating[0] in ['F', 'G']:
        return -40
        
    if rating[0] == 'A':
        scoring = 80
    elif rating[0] == 'B':
        scoring = 50
    elif rating[0] == 'C':
        scoring = 20
    elif rating[0] == 'D':
        scoring = -10
    elif rating[0] == 'E':
        scoring = -30

    if (len(rating) < 2):
        return scoring
      
    if rating[1] == '1':
        scoring += 20
    elif rating[1] == '2':
        scoring += 10
    elif rating[1] == '3':
        scoring += 0
            
    return scoring


def distance_score(duration):
    if duration <= 400:
        # Return a linear score between 200 and 250
        return 200 + (400 - duration) * 1/8.0
    else:
        return 100 * (30 * 60 - duration) / (30 * 60.0)
    

def price_score(price):
    return -75 * (abs(2100 - price) / 300.0)**2


# Create cache and output folders if they don't exist
os.makedirs(CACHE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Check if skip argument is provided
if not (len(sys.argv) > 1 and sys.argv[1].lower().startswith("skip")):
    print("Fetching rental data")
    get_daft_location("dublin")

if not (len(sys.argv) > 1 and sys.argv[1] == "skipAll"):
    print("Rating properties")
    rate_properties()

with open(os.path.join(OUTPUT_FOLDER, "dublin.json"), "r") as f:
    properties_with_ratings = json.load(f)
    ranked_listings = [score_property(property) for property in properties_with_ratings]
    ranked_listings.sort(key=lambda x: x[1], reverse=True)
    for listing in ranked_listings:
        print(f"{listing[0]} - {listing[1]}")
