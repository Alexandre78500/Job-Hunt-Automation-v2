from __future__ import annotations

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from src.utils.config import load_env, project_root


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main() -> None:
    load_env()

    credentials_path = Path(
        os.getenv("GMAIL_CREDENTIALS_PATH", str(project_root() / "credentials" / "gmail_credentials.json"))
    )
    token_path = Path(
        os.getenv("GMAIL_TOKEN_PATH", str(project_root() / "credentials" / "gmail_token.json"))
    )

    if not credentials_path.exists():
        print(f"Missing credentials file: {credentials_path}")
        print("Download OAuth client JSON from Google Cloud Console and place it there.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token saved to {token_path}")


if __name__ == "__main__":
    main()
