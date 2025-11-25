"""Unit tests for error handling and edge cases in the telemetry adapter."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch, ANY

import pytest

from exegesis.infrastructure.api.app.adapters.telemetry import ApiTelemetryProvider


class TestTelemetryErrorHandling:
    """Verify that the telemetry provider fails gracefully under error conditions."""

    @pytest.fixture
    def provider(self):
        p = ApiTelemetryProvider()
        p._workflow_runs = MagicMock()
        p._workflow_latency = MagicMock()
        return p

    @pytest.fixture
    def mock_logger(self, provider):
        provider._logger = MagicMock(spec=logging.Logger)
        return provider._logger

    def test_instrument_workflow_handles_span_creation_failure(self, provider, mock_logger):
        """Should not crash if the tracer fails to create a span."""
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.side_effect = RuntimeError("Tracer unavailable")

        # We need to mock _get_tracer to return our broken tracer
        with patch.object(provider, "_get_tracer", return_value=mock_tracer):
            # The context manager itself might raise if start_as_current_span fails immediately
            # But the design of instrument_workflow calls start_as_current_span inside the generator

            ctx = provider.instrument_workflow("test_workflow")

            # attempting to enter the context should raise the error,
            # but we want to verify it's logged if it happens inside our wrapper?
            # Actually looking at the code:
            # with tracer.start_as_current_span(...) as span:
            # If that raises, it bubbles up. The wrapper doesn't catch span creation errors,
            # only errors *inside* the span block (the yield).

            with pytest.raises(RuntimeError, match="Tracer unavailable"):
                with ctx:
                    pass

    def test_instrument_workflow_handles_user_code_failure(self, provider, mock_logger):
        """Should record exception and set status on span when user code fails."""
        mock_span = MagicMock()
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with patch.object(provider, "_get_tracer", return_value=mock_tracer):
            with pytest.raises(ValueError, match="Business logic failed"):
                with provider.instrument_workflow("test_workflow"):
                    raise ValueError("Business logic failed")

            # Verification
            mock_span.record_exception.assert_called()
            # Should log the failure
            mock_logger.exception.assert_called_with(
                "workflow.failed",
                extra=ANY
            )
            # Should still update metrics in finally block
            assert provider._workflow_runs.labels.called
            # Status passed to labels should be 'failed' because of the exception
            call_args = provider._workflow_runs.labels.call_args[1]
            assert call_args["status"] == "failed"

    def test_set_span_attribute_handles_exceptions(self, provider, mock_logger):
        """Should log debug message if setting attribute fails."""
        mock_span = MagicMock()
        mock_span.set_attribute.side_effect = TypeError("Invalid attribute type")

        provider.set_span_attribute(mock_span, "key", "value")

        mock_logger.debug.assert_called_with(
            "failed to set span attribute",
            extra={"key": "key", "value": "value"}
        )

    def test_record_counter_handles_exceptions(self, provider, mock_logger):
        """Should log debug message if recording counter fails."""
        # Mock the cache to return a broken metric
        mock_metric = MagicMock()
        mock_metric.labels.side_effect = ValueError("Invalid label")

        with patch.dict(provider._counter_cache, {("test_metric", ("label",)): mock_metric}):
            provider.record_counter("test_metric", labels={"label": "val"})

            mock_logger.debug.assert_called_with(
                "failed to record counter",
                extra={"metric": "test_metric", "labels": {"label": "val"}}
            )

    def test_record_histogram_handles_exceptions(self, provider, mock_logger):
        """Should log debug message if recording histogram fails."""
        mock_metric = MagicMock()
        mock_metric.labels.return_value.observe.side_effect = RuntimeError("Metric system down")

        with patch.dict(provider._histogram_cache, {("test_hist", ("tag",)): mock_metric}):
            provider.record_histogram("test_hist", value=1.5, labels={"tag": "A"})

            mock_logger.debug.assert_called_with(
                "failed to record histogram",
                extra={"metric": "test_hist", "labels": {"tag": "A"}}
            )

    def test_instrument_workflow_handles_status_setting_failure(self, provider, mock_logger):
        """Should swallow errors when setting span status fails (defensive coding)."""
        mock_span = MagicMock()
        # Mock set_status to raise exception
        mock_span.set_status.side_effect = AttributeError("Old SDK version")

        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        # We need Status/StatusCode to be present for the code to attempt set_status
        with patch("exegesis.infrastructure.api.app.adapters.telemetry.Status", MagicMock()), \
             patch("exegesis.infrastructure.api.app.adapters.telemetry.StatusCode", MagicMock()), \
             patch.object(provider, "_get_tracer", return_value=mock_tracer):

            with pytest.raises(RuntimeError):
                with provider.instrument_workflow("test_workflow"):
                    raise RuntimeError("Boom")

            # Should have tried to set status
            mock_span.set_status.assert_called()
            # Should have logged the failure to set status
            mock_logger.debug.assert_called_with(
                "failed to set span status",
                exc_info=True
            )

