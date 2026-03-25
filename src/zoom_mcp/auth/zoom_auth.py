"""Zoom authentication module for MCP server."""
import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__ )


class ZoomAuth:
    """Handles Zoom OAuth 2.0 Server-to-Server authentication."""

    def __init__(self, api_key: str, api_secret: str, account_id: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def get_access_token(self) -> str:
        """Get a valid access token (async)."""
        if self._is_token_valid():
            return self._token
        return await self._generate_token()

    def _is_token_valid(self) -> bool:
        if not self._token or not self._token_expiry:
            return False
        return datetime.now() < (self._token_expiry - timedelta(minutes=5))

    async def _generate_token(self) -> str:
        """Generate a new access token using Server-to-Server OAuth2."""
        credentials = base64.b64encode(
            f"{self.api_key}:{self.api_secret}".encode()
        ).decode()

        async with httpx.AsyncClient( ) as client:
            response = await client.post(
                "https://zoom.us/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "account_credentials",
                    "account_id": self.account_id,
                },
                timeout=10.0,
             )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to get OAuth token: {response.status_code} - {response.text}"
                )

            data = response.json()

        self._token = data["access_token"]
        self._token_expiry = datetime.now() + timedelta(seconds=data["expires_in"])
        logger.info("Zoom access token refreshed successfully.")
        return self._token

    @classmethod
    def from_env(cls) -> "ZoomAuth":
        api_key = os.getenv("ZOOM_API_KEY")
        api_secret = os.getenv("ZOOM_API_SECRET")
        account_id = os.getenv("ZOOM_ACCOUNT_ID")
        if not api_key or not api_secret:
            raise ValueError("ZOOM_API_KEY and ZOOM_API_SECRET must be set")
        if not account_id:
            raise ValueError("ZOOM_ACCOUNT_ID must be set")
        return cls(api_key=api_key, api_secret=api_secret, account_id=account_id)
