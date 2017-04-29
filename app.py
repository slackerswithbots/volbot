import json
import os
import requests
import sys

from flask import Flask, request

app = Flask(__name__)


@app.route('/', methods=['GET'])
def verify():
    """When the endpoint is registered as a webhook, it echos a value back."""
    if requests.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not requests.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():
    """Endpoint for processing incoming messaging events."""
    data = request.get_json()
    log(data)

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get('message'):  # someone sent us a message
                    sender_id = messaging_event["se nder"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    message_text = messaging_event["message"]["text"]

                    send_message(sender_id, "roger roger!")

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


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
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(msg):
    """Simple function for logging messages to the console."""
    print(str(msg))
    sys.stdout.flush()


if __name__ == "__main__":
    app.run(debug=True)
