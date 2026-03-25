"""Zoom Recordings Tool"""
import logging
import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from zoom_mcp.auth.zoom_auth import ZoomAuth

logger = logging.getLogger(__name__)


class GetRecordingTranscriptParams(BaseModel):
    recording_url: str = Field(..., description="URL of the Zoom recording")
    include_speaker_labels: bool = Field(True, description="Include speaker labels")


class RecordingTranscriptResponse(BaseModel):
    meeting_id: str
    topic: str = ""
    meeting_duration: int = 0
    transcripts: List[Dict[str, Any]]
    status: str = "success"


def extract_recording_id(recording_url: str) -> str:
    pattern = r"zoom\.us/rec/(?:share|play)/([a-zA-Z0-9_\-=+/]+)"
    match = re.search(pattern, recording_url)
    if not match:
        raise ValueError(f"Could not extract recording ID from URL: {recording_url}")
    return match.group(1)


async def get_recording_transcript(
    params: GetRecordingTranscriptParams,
) -> RecordingTranscriptResponse:
    import httpx

    recording_id = extract_recording_id(params.recording_url )
    logger.info(f"Retrieving transcript for recording ID: {recording_id}")

    zoom_auth = ZoomAuth.from_env()
    access_token = await zoom_auth.get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient( ) as client:
        response = await client.get(
            f"https://api.zoom.us/v2/meetings/{recording_id}/recordings",
            headers=headers,
            timeout=15.0,
         )

        if response.status_code == 404:
            account_id = zoom_auth.account_id
            response = await client.get(
                f"https://api.zoom.us/v2/accounts/{account_id}/recordings/{recording_id}",
                headers=headers,
                timeout=15.0,
             )

        if response.status_code != 200:
            raise Exception(
                f"Failed to retrieve recording: {response.status_code} - {response.text}"
            )

        data = response.json()
        recording_files = data.get("recording_files", [])
        transcript_files = [
            f for f in recording_files
            if f.get("file_type", "").upper() in ("TRANSCRIPT", "VTT")
        ]

        transcripts = []
        for tf in transcript_files:
            entry: Dict[str, Any] = {
                "file_id": tf.get("id", ""),
                "file_type": tf.get("file_type", ""),
                "recording_start": tf.get("recording_start", ""),
                "recording_end": tf.get("recording_end", ""),
            }
            download_url = tf.get("download_url")
            if download_url:
                try:
                    dl = await client.get(
                        download_url, headers=headers,
                        timeout=30.0, follow_redirects=True
                    )
                    if dl.status_code == 200:
                        entry["transcript_text"] = dl.text
                except Exception as e:
                    logger.warning(f"Could not download transcript: {e}")
                    entry["download_url"] = download_url
            transcripts.append(entry)

        return RecordingTranscriptResponse(
            meeting_id=str(data.get("id", recording_id)),
            topic=data.get("topic", ""),
            meeting_duration=data.get("duration", 0),
            transcripts=transcripts,
            status="success",
        )
