import json
import os
from dotenv import load_dotenv
from openai import OpenAI

import openAIClient

# load environment variables
load_dotenv()

# Output files
CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "cache")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "output")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def rate_properties(city: str):
    properties_with_ratings = []
    properties = []
    travel_times = {}

    with open(os.path.join(CACHE_FOLDER, f"{city}.json"), "r") as f:
        propertiesFile = json.load(f)
        properties = propertiesFile['properties']

    with open(os.path.join(CACHE_FOLDER, f"{city}_travel_time.json"), "r") as f:
        travel_times = json.load(f)
    
    for property in properties:
        if property['seoFriendlyPath'] not in travel_times:
            print(f"Property {property['seoFriendlyPath']} not in travel times.")
            continue

        property_details = extract_property_details(property, travel_times[property['seoFriendlyPath']])
        if property_details is not None:
            properties_with_ratings.append(property_details)

    with open(os.path.join(OUTPUT_FOLDER, f"{city}.json"), "w") as f:
        json.dump(properties_with_ratings, f, indent=2)
    
def extract_property_details(property, travel_time: float):
    if ('price' not in property or 
        'ber' not in property or 
        'rating' not in property['ber'] or 
        'point' not in property or 
        'coordinates' not in property['point']):
        return None
    
    print(f"Processing property: {property['seoFriendlyPath']}")
    berRating = get_ber_rating(property['ber']['rating'])
    price = float(''.join(c for c in property['price'] if c.isdigit()))

    print(f"Asking OpenAI about property: {property['seoFriendlyPath']}. Travel time: {travel_time} seconds.")
    [lng, lat] = property['point']['coordinates']
    propertyRating = openAIClient.generate_property_rating(client, lng, lat)

    print(f"Property: {property['seoFriendlyPath']}. Price: {price}. BER Rating: {berRating}. Public Travel Time: {travel_time} seconds. Safety Rating: {propertyRating.safetyRating}. Gym Rating: {propertyRating.gymRating}. Restaurants Rating: {propertyRating.restaurantsRating}. Outdoors Rating: {propertyRating.outdoorsRating}.")

    return {
        "name": property['seoFriendlyPath'],
        "price": price,
        "berRating": berRating,
        "publicTravelTime": travel_time,
        "safetyRating": propertyRating.safetyRating,
        "gymRating": propertyRating.gymRating,
        "restaurantsRating": propertyRating.restaurantsRating,
        "outdoorsRating": propertyRating.outdoorsRating,
    }

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