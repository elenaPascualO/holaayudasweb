"""Tests for email notification service."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.email_notify import send_sync_failure_email


@pytest.mark.asyncio
async def test_send_failure_email_when_configured():
    """Should send email when SMTP is configured."""
    with (
        patch("backend.services.email_notify._is_configured", return_value=True),
        patch("backend.services.email_notify._send_email") as mock_send,
    ):
        await send_sync_failure_email("convocatorias", "Connection timeout", mode="daily")

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert "convocatorias" in args[0]
        assert "daily" in args[0]
        assert "Connection timeout" in args[1]


@pytest.mark.asyncio
async def test_send_failure_email_beneficiarios():
    """Should include sync type in subject."""
    with (
        patch("backend.services.email_notify._is_configured", return_value=True),
        patch("backend.services.email_notify._send_email") as mock_send,
    ):
        await send_sync_failure_email("beneficiarios", "OOM error")

        subject = mock_send.call_args[0][0]
        assert "beneficiarios" in subject
        assert "mode" not in subject


@pytest.mark.asyncio
async def test_skip_when_not_configured():
    """Should silently skip when SMTP is not configured."""
    with (
        patch("backend.services.email_notify._is_configured", return_value=False),
        patch("backend.services.email_notify._send_email") as mock_send,
    ):
        await send_sync_failure_email("convocatorias", "error")

        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_email_send_failure_does_not_raise():
    """Should catch and log exceptions from SMTP, not propagate."""
    with (
        patch("backend.services.email_notify._is_configured", return_value=True),
        patch(
            "backend.services.email_notify._send_email",
            side_effect=ConnectionRefusedError("SMTP down"),
        ),
    ):
        # Should not raise
        await send_sync_failure_email("convocatorias", "some error", mode="daily")
