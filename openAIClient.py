from pydantic import BaseModel
from openai import OpenAI

class PropertyRating(BaseModel):
    safetyRating: int
    gymRating: int
    restaurantsRating: int
    outdoorsRating: int

def generate_property_rating(client: OpenAI, lng: float, lat: float):
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