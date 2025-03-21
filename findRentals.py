import sys
import json
import os
import scrapRentalData
import extractPropertyDetails


def score_property(property_details):
    distanceScore = distance_score(property_details['publicTravelTime'])
    ber_score = property_details['berRating']
    priceScore= price_score(property_details['price'])
    score = priceScore + ber_score + distanceScore + 25 * (property_details['safetyRating'] + property_details['gymRating'] + property_details['restaurantsRating'] + property_details['outdoorsRating'])
    return property_details['name'], score


def distance_score(duration):
    if duration <= 400:
        # Return a linear score between 200 and 250
        return 200 + (400 - duration) * 1/8.0
    else:
        return 100 * (40 * 60 - duration) / (40 * 60.0)
    

def price_score(price):
    return -50 * (abs(2100 - price) / 300.0)**2

# Output files
CACHE_FOLDER = os.path.join(os.path.dirname(__file__), "cache")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "output")

# Create cache and output folders if they don't exist
os.makedirs(CACHE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

target_city = "dublin-city" 

# Check if skip argument is provided
if not (len(sys.argv) > 1 and sys.argv[1].lower().startswith("skip")):
    print("Fetching rental data")
    scrapRentalData.get_daft_location(target_city)

if not (len(sys.argv) > 1 and sys.argv[1] == "skipAll"):
    print("Rating properties")
    extractPropertyDetails.rate_properties(target_city)

with open(os.path.join(OUTPUT_FOLDER, f"{target_city}.json"), "r") as f:
    properties_with_ratings = json.load(f)
    ranked_listings = [score_property(property) for property in properties_with_ratings]
    ranked_listings.sort(key=lambda x: x[1], reverse=True)
    for listing in ranked_listings:
        print(f"{listing[0]} - {listing[1]}")
