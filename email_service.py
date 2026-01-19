import os
import requests

def send_email(to_email, subject, html_content):
    api_key = os.getenv("BREVO_API_KEY")
    sender = os.getenv("EMAIL_SENDER")

    if not api_key or not sender:
        print("Email disabled (missing API key)")
        return

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    data = {
        "sender": {"email": sender},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }

    requests.post(url, json=data, headers=headers)
