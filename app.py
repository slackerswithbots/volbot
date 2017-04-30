"""Main app script."""
import json
import os
import requests
import sys
import redis
import json

from flask import Flask, request, render_template
from pprint import pprint

app = Flask(__name__)
fb_graph = "https://graph.facebook.com/v2.6/me/messages"
cache = redis.from_url(os.environ.get("REDIS_URL"))
categories = ["black", "kids", "tech", "homeless", "cleanup", "donation"]

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
                        response = handle_attachments(context)

                    except:
                        response = "I wasn't able to process that last message. Can you send it again?"

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


def send_message(recipient_id, msg_text):
    """Send a message to a given person."""
    log(f"Sending message to {recipient_id}: {msg_text}")

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
        "message": {
            "text": msg_text
        }
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
    return "Hello my guy, how's it going? I will need your location to show you some volunteer opportunities near you."

def handle_attachments(context):
    """Handles whatever attachments are coming in and sends back a response."""
    return "Alright thanks! I see you are in Seattle. There a lot of events going on near you. What are you interested in? Our categories are " + str(categories)
    # get the attachment that has the location
    #locations = list(filter(lambda loc: loc['type'] == 'location', attachments))
    # if locations:
    #     loc = locations[0]
    #     coords = loc["payload"]["coordinates"]
    #     return str(coords)
    #
    # else:
    #     return "We couldn't find a location among your attachments."


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
    phi1 = convert_to_radians(point1[lat])
    phi2 = convert_to_radians(point2[lat])
    delta_phi = convert_to_radians(point1[lat] - point2[lat])
    delta_lam = convert_to_radians(point1[lon] - point2[lon])


    a = math.sin(0.5 * delta_phi)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(0.5 * delta_lam)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_earth * c / 1.60934 # convert km to miles

if __name__ == "__main__":
    app.run(debug=True)
