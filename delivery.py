"""
delivery.py
Component 5: Delivery Layer (WhatsApp Cloud API version)

Uses Meta's official, free-tier WhatsApp Cloud API to post the digest.

Free-tier mechanics you should know:
  - The test phone number Meta gives you can message any number you've
    added and verified as a "test recipient" in the app dashboard.
  - There's no true "post into a group" endpoint on the Cloud API - Meta's
    API sends to individual WhatsApp numbers/threads, not group chat IDs.
    The common way to satisfy "post into a WhatsApp group" on the free,
    ToS-compliant Cloud API is either:
      (a) send to each opted-in member individually (loop over a small
          contact list), or
      (b) use a WhatsApp *broadcast list* you control, which behaves like
          a group for recipients but is still 1:1 delivery under the hood.
    This module supports both via a list of recipient numbers in config.
  - Access tokens from API Setup are temporary (24h). For a scheduler that
    runs unattended, generate a permanent token via a System User in
    Meta Business Settings and use that instead.
"""

import os
import requests


def send_whatsapp_message(message: str, config: dict) -> bool:
    wa_cfg = config.get("whatsapp_cloud_api", {})
    phone_number_id = os.environ.get(wa_cfg.get("phone_number_id_env", "WHATSAPP_PHONE_NUMBER_ID"))
    access_token = os.environ.get(wa_cfg.get("access_token_env", "WHATSAPP_TOKEN"))
    recipients_env = os.environ.get(wa_cfg.get("recipients_env", "WHATSAPP_RECIPIENTS"), "")
    recipients = [r.strip() for r in recipients_env.split(",") if r.strip()] or wa_cfg.get("recipients", [])

    if not phone_number_id or not access_token or not recipients:
        print("[delivery] WhatsApp Cloud API config/secrets missing - skipping send")
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}

    all_ok = True
    for number in recipients:
        payload = {
            "messaging_product": "whatsapp",
            "to": number,
            "type": "text",
            "text": {"body": message},
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            print(f"[delivery] sent to {number}")
        except Exception as e:
            print(f"[delivery] send to {number} failed: {e}")
            all_ok = False

    return all_ok
