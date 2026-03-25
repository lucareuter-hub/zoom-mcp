"""
Zoom MCP Server
This module provides the main implementation of the Zoom MCP server.
"""
import json
import logging
import os

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from zoom_mcp.auth.zoom_auth import ZoomAuth
from zoom_mcp.resources.recordings import RecordingListParams, RecordingResource
from zoom_mcp.tools.recordings import (
    GetRecordingTranscriptParams,
    get_recording_transcript as get_recording_transcript_tool,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Prüft bei jedem Request ob ein gültiger Bearer Token mitgeschickt wird."""

    async def dispatch(self, request: Request, call_next):
        secret = os.environ.get("MCP_SECRET_TOKEN")
        if secret:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {secret}":
                logger.warning(
                    f"Unauthorized request from {request.client.host} "
                    f"to {request.url.path}"
                )
                return Response("Unauthorized", status_code=401)
        return await call_next(request)


class SecureFastMCP(FastMCP):
    """FastMCP mit eingebautem Bearer Token Schutz."""

    async def run_sse_async(self, mount_path=None):
        starlette_app = self.sse_app(mount_path)
        starlette_app.add_middleware(BearerTokenMiddleware)
        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()


class ZoomMCP:
    def __init__(self):
        try:
            self.auth_manager = ZoomAuth.from_env()
            host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
            port = int(os.environ.get("PORT", os.environ.get("FASTMCP_PORT", "8000")))
            self.mcp_server = SecureFastMCP("Zoom", host=host, port=port)
            self.name = "Zoom"
            self._register_resources()
            self._register_tools()

            if os.environ.get("MCP_SECRET_TOKEN"):
                logger.info("Bearer token authentication is ENABLED.")
            else:
                logger.warning("MCP_SECRET_TOKEN is not set — server is UNPROTECTED.")

        except Exception as e:
            logger.error(f"Error initializing Zoom MCP server: {str(e)}")
            raise

    def _register_resources(self):
        recording_resource = RecordingResource(self.auth_manager)

        @self.mcp_server.resource("recordings://list")
        async def list_recordings() -> str:
            """List recordings from Zoom"""
            recordings = await recording_resource.list_recordings(RecordingListParams())
            return json.dumps(recordings)

        @self.mcp_server.resource("recording://{recording_id}")
        async def get_recording(recording_id: str) -> str:
            """Get a specific recording from Zoom"""
            recording = await recording_resource.get_recording(recording_id)
            return json.dumps(recording)

    def _register_tools(self):
        @self.mcp_server.tool()
        async def get_recording_transcript(params: GetRecordingTranscriptParams) -> str:
            """Get the transcript for a Zoom recording."""
            try:
                transcript_data = await get_recording_transcript_tool(params)
                return json.dumps(transcript_data.dict())
            except Exception as e:
                logger.error(f"Error in get_recording_transcript tool: {str(e)}")
                raise

    def start(self, transport: str = "sse"):
        """Start the MCP server. Defaults to SSE for remote deployments."""
        self.mcp_server.run(transport=transport)

    def stop(self):
        pass


def create_zoom_mcp() -> ZoomMCP:
    return ZoomMCP()


load_dotenv()

try:
    server = create_zoom_mcp()
except Exception as e:
    logger.error(f"Error creating Zoom MCP server: {str(e)}")
    server = None

if __name__ == "__main__":
    try:
        mcp_server = create_zoom_mcp()
        mcp_server.start(transport="sse")
    except Exception as e:
        logger.error(f"Error starting Zoom MCP server: {str(e)}")
        import sys
        sys.exit(1)
