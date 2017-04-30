"""Main app script."""
import geocoder
import json
import os
import re
import redis
import requests
import sys

from flask import Flask, request, render_template
from pprint import pprint


app = Flask(__name__)
fb_graph = "https://graph.facebook.com/v2.6/me/messages"
cache = redis.from_url(os.environ.get("REDIS_URL"))
categories = {
    '101': 'Business',
    '102': 'Science & Tech',
    '103': 'Music',
    '104': 'Film & Media',
    '105': 'Arts',
    '106': 'Fashion',
    '107': 'Health',
    '108': 'Sports & Fitness',
    '109': 'Travel & Outdoor',
    '110': 'Food & Drink',
    '111': 'Charity & Causes',
    '112': 'Government',
    '113': 'Community',
    '114': 'Spirituality',
    '115': 'Family & Education',
    '116': 'Holiday',
    '117': 'Home & Lifestyle',
    '118': 'Auto, Boat & Air',
    '119': 'Hobbies',
    '199': 'Other'
}
city_state_pattern = '[\w+\.+\-+\s+]+\,\s{1}\w{2}'


@app.route('/', methods=['GET'])
def verify():
    """When the endpoint is registered as a webhook, it echos a value back."""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return 'Youre good', 200


@app.route('/', methods=['POST'])
def webhook():
    """Endpoint for processing incoming messaging events."""
    data = request.get_json()
    log(data)

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get('message'):  # someone sent us a message
                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    response = ""

                    try:
                        message_text = messaging_event["message"]["text"]
                        context = cache_helper(cache, messaging_event, "text")
                        response = handle_msg(context)

                    except KeyError:
                        context = cache_helper(cache, messaging_event, "location")
                        #attachments = messaging_event["message"]["attachments"]
                        response = handle_location(context)

                    except:
                        response = {"text": "I wasn't able to process that last message. Can you send it again?"}

                    finally:
                        send_message(sender_id, response)

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


@app.route('/privacy', methods=['GET'])
def privacy():
    return 'boo', 200


def send_message(recipient_id, msg):
    """Send a message to a given person."""
    log(f"Sending message to {recipient_id}: {str(msg)}")

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": msg,
    })
    r = requests.post(fb_graph, params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def cache_helper(cache, event, action):
        context = {} # Context dict
        user_id = event["sender"]["id"]
        user_msg = ""
        user_loc = {}
        log("\n\n\n\n" + str(event))
        if action == "text":
            user_msg = event["message"]["text"]
        if action == "location":
            user_loc = event["message"]["attachments"][0]["payload"]["coordinates"]
        if cache.get(user_id):
            cached_context = json.loads(str(cache.get(user_id), 'utf-8'))
            cached_context["msg"].append(user_msg)
            if user_loc:
                cached_context["loc"] = user_loc
            cache.set(user_id, json.dumps(cached_context))
            return cached_context
        else:
            context["id"] =  user_id
            context["msg"] = [user_msg]
            context["loc"] = user_loc
            cache.set(user_id, json.dumps(context))
            return context

def handle_msg(context):
    """Returns an appropriate response for an incoming message."""
    all_messages = context["msg"]
    cats = [val.lower() for val in categories.values()]

    if  "hey volbot" in all_messages[-1].lower():
        return {
        	"text": "Hello my guy, how's it going? Send me your location so I can show you some volunteer opportunities near you. If you can't hit the button below, just send me your city and state (e.g. Seattle, WA) and we can figure it out from there.",
            "quick_replies": [
                {
                    "content_type": "location",
                }
            ]
        }

    elif sum([word in cats for word in all_messages[-1].split(' ')]) > 0:
        cat = "environmentalism"
        events = [
            "Uncle Bob's Glorious Tree-Saving Adventure",
            "Feed some homeless dudes",
            "Mentor some kids",
            "Build a Hooverville",
            "Give poor grad students money"
        ]
        outstr = f"Cool! Here's the next 5 events related to {cat} near you:\n"
        for event in events:
            outstr += f"\t-{event}\n"
        return {
            "text": outstr
        }

    elif re.findall(city_state_pattern, all_messages[-1]):
        city_state = re.findall(city_state_pattern, all_messages[-1])[0]
        return handle_city_state(city_state, context)

    else:
        return {
        	"text": "Sorry, I didn't quite get that last message. Can I get your location, or a volunteer event category?"
        }


def get_events_from_api(context):
    """Given some latitude and longitude, retrieve events from some API."""
    payload = {
        'token': "MLPUWPRFF6K7XDTVINAG",
        'location.latitude': context['loc']['lat'],
        'location.longitude': context['loc']['long'],
        'location.within': '10mi',
        'q': 'volunteer'
    }
    response = requests.get("https://www.eventbriteapi.com/v3/events/search/", params=payload)
    events = json.loads(response.content)['events']
    return events


def handle_city_state(city_state, context):
    """Receives a zip code and returns events for that city/state."""
    geo_info = geocoder.google(city_state)
    context["loc"] = {'lat': geo_info.lat, 'long': geo_info.lng}

    events = get_events_from_api(context)

    nearby_cats = set()
    for event in events:
        if event['category_id']:
            nearby_cats.add(categories[event["category_id"]])

    context['events'] = events
    cache.set(context["id"], json.dumps(context))

    output_str = f"Alright thanks! There's {len(events)} events going on near {geo_info.city}, {geo_info.state}. What are you interested in? Our categories are:\n"

    for cat in nearby_cats:
        output_str += f'\t- {cat}\n'

    return {
        "text": output_str
    }


def handle_location(context):
    """Handles whatever location object is sent in."""
    loc = context["loc"]
    geo_info = geocoder.google([loc['lat'], loc['long']], method="reverse")

    events = get_events_from_api(loc['lat'], loc['long'])

    nearby_cats = set()
    for event in events:
        if event['category_id']:
            nearby_cats.add(categories[event["category_id"]])

    context['events'] = events
    cache.set(context["id"], json.dumps(context))

    output_str = f"Alright thanks! I've looked you up, and can see that you are in {geo_info.city}, {geo_info.state}. There's {len(events)} events going on near you. What are you interested in? Our categories are:\n"

    for cat in nearby_cats:
        output_str += f'\t- {cat}\n'

    return {
    	"text": output_str
    }


def is_close(event, user_location, miles=10):
    """Return boolean about whether or not the event is within given miles."""
    event_loc = {'long': float(event['long']), 'lat': float(event['lat'])}
    return calculate_distance(event_loc, user_location) <= miles


def log(msg):
    """Simple function for logging messages to the console."""
    pprint(str(msg))
    sys.stdout.flush()


def calculate_distance(point1, point2):
    """
    Calculate the distance (in miles) between point1 and point2.
    point1 and point2 must have the format {latitude, longitude}.
    The return value is a float.

    Modified and converted to Python from: http://www.movable-type.co.uk/scripts/latlong.html
    """
    import math

    def convert_to_radians(degrees):
        return degrees * math.pi / 180

    radius_earth = 6.371E3 # km
    phi1 = convert_to_radians(point1["lat"])
    phi2 = convert_to_radians(point2["lat"])
    delta_phi = convert_to_radians(point1["lat"] - point2["lat"])
    delta_lam = convert_to_radians(point1["long"] - point2["long"])


    a = math.sin(0.5 * delta_phi)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(0.5 * delta_lam)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_earth * c / 1.60934 # convert km to miles

if __name__ == "__main__":
    app.run(debug=True)
