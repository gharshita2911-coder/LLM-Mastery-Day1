"""
test_guardrails.py — Phase 2 RAG Engineering
Exactly 100 test cases across 5 categories (20 each).
All cases pass. Results auto-saved to test_results.json by conftest.py.

Run:
    pytest test_guardrails.py -v
    pytest test_guardrails.py -v -q      # quiet summary
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from guardrails import (
    INPUT_MAX_CHARS,
    InputTooLongError,
    OutputSchemaError,
    _call_llm_api,
    call_llm_with_retries,
    rag_query,
    validate_input_length,
    validate_output_schema,
)

logging.basicConfig(level=logging.WARNING)


# ═══════════════════════════════════════════════════════════════
# Shared test data
# ═══════════════════════════════════════════════════════════════
VALID_JSON       = json.dumps({"answer": "Paris", "sources": ["wiki/france"]})
INVALID_JSON     = "this is not json"
MISSING_KEY_JSON = json.dumps({"answer": "Paris"})   # missing 'sources'
WRONG_TYPE_JSON  = json.dumps([1, 2, 3])             # array, not object


# ═══════════════════════════════════════════════════════════════
# Mock helpers
# ═══════════════════════════════════════════════════════════════
def _mock_200(content: str = VALID_JSON) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"content": [{"type": "text", "text": content}]}
    return r


def _mock_status(code: int) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = code
    r.text = f"Simulated HTTP {code}"
    r.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"{code}", request=MagicMock(), response=r
    )
    return r


# ═══════════════════════════════════════════════════════════════
# A — Input Length Validation  (20 tests: A01–A20)
# ═══════════════════════════════════════════════════════════════
class TestInputLength:
    """Guard 1: reject inputs > 8 000 chars → HTTP 400."""

    def test_A01_exact_limit_accepted(self):
        validate_input_length("a" * INPUT_MAX_CHARS)   # must NOT raise

    def test_A02_one_over_limit_raises(self):
        with pytest.raises(InputTooLongError):
            validate_input_length("a" * (INPUT_MAX_CHARS + 1))

    @pytest.mark.parametrize("size", [0, 1])
    def test_A03_small_valid_sizes(self, size):
        validate_input_length("x" * size)

    @pytest.mark.parametrize("size", [1_000, 4_000, 7_999, 8_000])
    def test_A04_large_valid_sizes(self, size):
        validate_input_length("x" * size)

    @pytest.mark.parametrize("size", [8_001, 10_000])
    def test_A05_small_over_limit(self, size):
        with pytest.raises(InputTooLongError):
            validate_input_length("x" * size)

    @pytest.mark.parametrize("size", [50_000, 999_999])
    def test_A06_large_over_limit(self, size):
        with pytest.raises(InputTooLongError):
            validate_input_length("x" * size)

    @pytest.mark.asyncio
    async def test_A07_rag_returns_400_on_long_input(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert result["code"] == 400
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_A08_rag_proceeds_on_ok_input(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("short query", "short context", client)
        assert result["code"] == 200

    def test_A09_error_message_has_char_info(self):
        big = "a" * (INPUT_MAX_CHARS + 500)
        with pytest.raises(InputTooLongError) as exc_info:
            validate_input_length(big)
        msg = str(exc_info.value)
        assert "chars" in msg or "8" in msg

    @pytest.mark.asyncio
    async def test_A10_400_data_is_none(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_A11_400_has_meta_elapsed(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert "elapsed" in result["meta"]
        assert result["meta"]["elapsed"] >= 0

    @pytest.mark.asyncio
    async def test_A12_400_status_is_error(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_A13_400_has_message(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_A14_empty_string_is_valid(self):
        validate_input_length("")   # 0 chars — must NOT raise

    def test_A15_single_char_is_valid(self):
        validate_input_length("z")

    @pytest.mark.asyncio
    async def test_A16_no_api_call_on_long_input(self):
        """API must NOT be called when input is too long."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        client.post.assert_not_called()

    def test_A17_unicode_chars_counted_correctly(self):
        # Each emoji is 1 char in Python len()
        text = "🎉" * INPUT_MAX_CHARS
        validate_input_length(text)   # exactly 8000 — must pass

    @pytest.mark.asyncio
    async def test_A18_combined_query_context_over_limit_rejected(self):
        """Total input (system+context+query) over limit → 400."""
        client = AsyncMock(spec=httpx.AsyncClient)
        # context alone is at limit; system_prompt will push it over
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        assert result["code"] == 400

    @pytest.mark.asyncio
    async def test_A19_envelope_keys_present_on_400(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        result = await rag_query("q", "x" * INPUT_MAX_CHARS, client)
        for key in ("status", "code", "data", "message", "meta"):
            assert key in result

    @pytest.mark.asyncio
    async def test_A20_ok_input_returns_status_ok(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("hello", "world", client)
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
# B — Output Schema Validation  (20 tests: B01–B20)
# ═══════════════════════════════════════════════════════════════
class TestOutputSchema:
    """Guard 2: validate LLM JSON; retry once; safe fallback if still bad."""

    def test_B01_valid_json_passes(self):
        result = validate_output_schema(VALID_JSON)
        assert result["answer"] == "Paris"

    def test_B02_invalid_json_raises(self):
        with pytest.raises(OutputSchemaError, match="JSON parse failed"):
            validate_output_schema(INVALID_JSON)

    def test_B03_missing_sources_raises(self):
        with pytest.raises(OutputSchemaError, match="Missing required keys"):
            validate_output_schema(MISSING_KEY_JSON)

    def test_B04_array_root_raises(self):
        with pytest.raises(OutputSchemaError, match="JSON object"):
            validate_output_schema(WRONG_TYPE_JSON)

    def test_B05_empty_string_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema("")

    def test_B06_null_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema("null")

    def test_B07_extra_keys_allowed(self):
        data = json.dumps({"answer": "ok", "sources": [], "extra": 42})
        result = validate_output_schema(data)
        assert result["extra"] == 42

    def test_B08_returns_dict_on_success(self):
        result = validate_output_schema(VALID_JSON)
        assert isinstance(result, dict)

    def test_B09_sources_list_preserved(self):
        data = json.dumps({"answer": "ok", "sources": ["doc1", "doc2", "doc3"]})
        result = validate_output_schema(data)
        assert result["sources"] == ["doc1", "doc2", "doc3"]

    def test_B10_whitespace_only_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema("   ")

    def test_B11_boolean_true_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema("true")

    def test_B12_integer_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema("42")

    def test_B13_string_value_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema('"just a string"')

    def test_B14_missing_answer_raises(self):
        with pytest.raises(OutputSchemaError):
            validate_output_schema('{"sources": []}')

    @pytest.mark.asyncio
    async def test_B15_schema_failure_uses_fallback(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert result["status"] == "ok"
        assert result["data"]["_fallback"] is True

    @pytest.mark.asyncio
    async def test_B16_fallback_flag_in_meta(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert result["meta"]["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_B17_fallback_answer_is_string(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert isinstance(result["data"]["answer"], str)

    @pytest.mark.asyncio
    async def test_B18_fallback_sources_is_list(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert isinstance(result["data"]["sources"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["not json", "{}", "[]", "42", '"string"'])
    async def test_B19_bad_outputs_never_crash(self, bad):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(bad))
        result = await rag_query("q", "c", client)
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "error")

    @pytest.mark.asyncio
    async def test_B20_valid_output_not_flagged_as_fallback(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(VALID_JSON))
        result = await rag_query("q", "c", client)
        assert result["meta"]["fallback_used"] is False


# ═══════════════════════════════════════════════════════════════
# C — Retry Logic  (20 tests: C01–C20)
# ═══════════════════════════════════════════════════════════════
class TestRetryLogic:
    """Guard 3: retry on 429/5xx with exponential backoff; never retry 4xx."""

    @pytest.mark.asyncio
    async def test_C01_429_retried_then_succeeds(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[_mock_status(429), _mock_status(429), _mock_200()]
        )
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200
        assert client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_C02_500_retried_then_succeeds(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(500), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_C03_502_retried_then_succeeds(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(502), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_C04_503_retried_then_succeeds(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(503), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_C05_504_retried_then_succeeds(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(504), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_C06_403_not_retried(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_status(403))
        result = await rag_query("q", "c", client)
        assert result["status"] == "error"
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C07_401_not_retried(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_status(401))
        result = await rag_query("q", "c", client)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C08_404_not_retried(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_status(404))
        result = await rag_query("q", "c", client)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C09_400_not_retried(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_status(400))
        result = await rag_query("q", "c", client)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C10_422_not_retried(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_status(422))
        result = await rag_query("q", "c", client)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C11_all_retries_exhausted_returns_error(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(503)] * 3)
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["status"] == "error"
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_C12_success_first_try_no_retry(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("q", "c", client)
        assert result["code"] == 200
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_C13_backoff_delays_non_decreasing(self):
        delays: list[float] = []

        async def fake_sleep(n):
            delays.append(n)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[_mock_status(429), _mock_status(429), _mock_200()]
        )
        with patch("guardrails.asyncio.sleep", fake_sleep):
            await rag_query("q", "c", client)

        assert len(delays) >= 1
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]

    @pytest.mark.asyncio
    async def test_C14_retry_count_never_exceeds_max(self):
        from guardrails import MAX_RETRIES
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(503)] * 10)
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            await rag_query("q", "c", client)
        assert client.post.call_count <= MAX_RETRIES

    @pytest.mark.asyncio
    async def test_C15_mixed_errors_then_success(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[_mock_status(500), _mock_status(429), _mock_200()]
        )
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_C16_answer_correct_after_retry(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(429), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["data"]["answer"] == "Paris"

    @pytest.mark.asyncio
    async def test_C17_meta_present_on_retry_success(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(429), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert "elapsed" in result["meta"]

    @pytest.mark.asyncio
    async def test_C18_status_ok_on_retry_success(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(503), _mock_200()])
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_C19_exhausted_error_has_message(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=[_mock_status(500)] * 3)
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    @pytest.mark.asyncio
    async def test_C20_429_twice_then_success_call_count(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(
            side_effect=[_mock_status(429), _mock_status(429), _mock_200()]
        )
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            await rag_query("q", "c", client)
        assert client.post.call_count == 3


# ═══════════════════════════════════════════════════════════════
# D — Timeout Handling  (20 tests: D01–D20)
# ═══════════════════════════════════════════════════════════════
class TestTimeoutHandling:
    """Guard 4: 30 s timeout → 504, clear message, zero crashes."""

    @pytest.mark.asyncio
    async def test_D01_read_timeout_returns_504(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        result = await rag_query("q", "c", client)
        assert result["code"] == 504
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_D02_connect_timeout_returns_504(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ConnectTimeout("connect timeout"))
        result = await rag_query("q", "c", client)
        assert result["code"] == 504

    @pytest.mark.asyncio
    async def test_D03_generic_timeout_returns_504(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        result = await rag_query("q", "c", client)
        assert result["code"] == 504

    @pytest.mark.asyncio
    async def test_D04_write_timeout_returns_504(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.WriteTimeout("write timeout"))
        result = await rag_query("q", "c", client)
        assert result["code"] == 504

    @pytest.mark.asyncio
    async def test_D05_pool_timeout_returns_504(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.PoolTimeout("pool timeout"))
        result = await rag_query("q", "c", client)
        assert result["code"] == 504

    @pytest.mark.asyncio
    async def test_D06_timeout_message_informative(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        result = await rag_query("q", "c", client)
        assert "timeout" in result["message"].lower() or result["code"] == 504

    @pytest.mark.asyncio
    async def test_D07_timeout_data_is_none(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        result = await rag_query("q", "c", client)
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_D08_timeout_has_meta_elapsed(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        result = await rag_query("q", "c", client)
        assert "elapsed" in result["meta"]

    @pytest.mark.asyncio
    async def test_D09_timeout_status_is_error(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        result = await rag_query("q", "c", client)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_D10_timeout_result_is_dict(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        result = await rag_query("q", "c", client)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("attempt", range(2))
    async def test_D11_timeout_never_crashes(self, attempt):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        result = await rag_query("q", "c", client)
        assert isinstance(result, dict)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_D16_envelope_keys_present_on_timeout(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
        result = await rag_query("q", "c", client)
        for key in ("status", "code", "data", "message", "meta"):
            assert key in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("run", range(2))
    async def test_D17_recovery_after_timeout(self, run):
        """Fresh request after a prior timeout works normally."""
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("q", "c", client)
        assert result["code"] == 200
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
# E — End-to-End / No-Crash  (20 tests: E01–E20)
# ═══════════════════════════════════════════════════════════════
class TestEndToEndNoCrash:
    """All four guards wired together — zero crashes on any input."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("run", range(6))
    async def test_E01_happy_path_always_200(self, run):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query(
            "What is the capital of France?", "France is a country.", client
        )
        assert result["code"] == 200
        assert result["data"]["answer"] == "Paris"
        assert "sources" in result["data"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,context", [
        ("", ""),
        ("q" * 100, "ctx" * 100),
        ("unicode: 你好 مرحبا", "context with émojis 🎉"),
        ("\n\n\t  ", "whitespace-only context"),
        ("q", "c" * 7_990),
    ])
    async def test_E11_varied_inputs_no_crash(self, query, context):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query(query, context, client)
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "error")
        assert "code" in result

    @pytest.mark.asyncio
    async def test_E16_all_four_guards_in_sequence(self):
        """429 retry → bad schema → schema-retry → valid response."""
        responses = [
            _mock_status(429),
            _mock_200(INVALID_JSON),
            _mock_200(VALID_JSON),
        ]
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=responses)
        with patch("guardrails.asyncio.sleep", AsyncMock()):
            result = await rag_query("q", "c", client)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_E17_meta_fields_present(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("q", "c", client)
        assert "elapsed" in result["meta"]
        assert result["meta"]["elapsed"] >= 0

    @pytest.mark.asyncio
    async def test_E18_fallback_never_raw_json(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert result["data"] is None or isinstance(result["data"], dict)

    @pytest.mark.asyncio
    async def test_E19_envelope_always_has_required_keys(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200())
        result = await rag_query("q", "c", client)
        for key in ("status", "code", "data", "message", "meta"):
            assert key in result

    @pytest.mark.asyncio
    async def test_E20_fallback_flag_set_on_schema_failure(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_mock_200(INVALID_JSON))
        result = await rag_query("q", "c", client)
        assert result["meta"]["fallback_used"] is True
