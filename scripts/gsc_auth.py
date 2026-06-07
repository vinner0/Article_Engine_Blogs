"""One-time OAuth flow — run manually to generate GSC refresh token."""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
CLIENT_SECRET = os.path.join(os.path.dirname(__file__), "../credentials/gsc_oauth_client.json")

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\nAdd these to credentials/.env:\n")
    print(f"GSC_CLIENT_ID={creds.client_id}")
    print(f"GSC_CLIENT_SECRET={creds.client_secret}")
    print(f"GSC_REFRESH_TOKEN={creds.refresh_token}")

if __name__ == "__main__":
    main()
