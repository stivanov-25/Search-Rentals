import os
import sys
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# work coordinates
WORK_LAT = os.getenv("WORK_LAT")
WORK_LON = os.getenv("WORK_LON")

class PropertyRating(BaseModel):
    price: int
    berRating: int
    travelTime: int
    safetyRating: int
    restaurantsRating: int
    outdoorsRating: int
    hasGym: bool
    hasWasher: bool
    hasDryer: bool
    hasDishwasher: bool
    isPetFriendly: bool

def generate_property_rating(url: str):
    systemPrompt = f"""
    You are a real estate agent.
    You are given a property and you need to provide some information about the property as well as rate it on some criteria (all ratings numbers should be between 0 and 100):
    - Price of the property
    - BER rating
    - Travel time to work: approximate time to travel from the property to the office in seconds.
    - Safety Rating (e.g. crime rate, safety of the area, etc.)
    - Rating on how close nearby gyms are
    - Restaurants and Cafes Rating
    - Outdoors Rating (e.g. parks, green spaces, etc.)
    - Whether the property has a gym
    - Whether the property has a washer
    - Whether the property has a dryer
    - Whether the property has a dishwasher
    - Whether the property is pet friendly
    """

    userPrompt = f"""
    My work is located at {WORK_LAT}, {WORK_LON}. Please look at the following property and provide the information requested.
    Property URL: {url}.
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



if len(sys.argv) > 1:
    url = sys.argv[1]
    rating = generate_property_rating(url)
    print(rating)
