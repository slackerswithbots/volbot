"""Main app script."""
import json
import os
import requests
import sys
import redis

from flask import Flask, request, render_template
from pprint import pprint

app = Flask(__name__)
fb_graph = "https://graph.facebook.com/v2.6/me/messages"

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
                        response = handle_msg(message_text)

                    except KeyError:
                        attachments = messaging_event["message"]["attachments"]
                        response = handle_attachments(attachments)

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


def handle_msg(msg):
    """Returns an appropriate response for an incoming message."""
    return "Hi!"

def handle_attachments(attachments):
    """Handles whatever attachments are coming in and sends back a response."""
    # get the attachment that has the location
    locations = list(filter(lambda loc: loc['type'] == 'location', attachments))
    if locations:
        loc = locations[0]
        coords = loc["payload"]["coordinates"]
        return str(coords)

    else:
        return "We couldn't find a location among your attachments."


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
