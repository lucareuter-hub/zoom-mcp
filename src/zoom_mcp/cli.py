"""
Zoom MCP CLI
This module provides a command-line interface for the Zoom MCP server.
"""
import argparse
import logging
import os
import sys
from typing import List, Optional

from zoom_mcp.server import create_zoom_mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zoom MCP Server")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "sse" ),
    )
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    parsed_args = parse_args(args)
    logging.getLogger().setLevel(getattr(logging, parsed_args.log_level))
    try:
        mcp_server = create_zoom_mcp()
        logger.info(f"Starting Zoom MCP server with transport={parsed_args.transport}")
        mcp_server.start(transport=parsed_args.transport)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
