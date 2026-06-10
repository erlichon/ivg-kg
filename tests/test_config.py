"""
Mechanical tests for config.py constants.
These tests have no external dependencies (stdlib + the ivg_kg package only).
"""

from ivg_kg import config


def test_sitelink_band_is_tuple_of_two_ints() -> None:
    lo, hi = config.SITELINK_BAND
    assert isinstance(lo, int)
    assert isinstance(hi, int)


def test_sitelink_band_values() -> None:
    lo, hi = config.SITELINK_BAND
    assert lo == 5
    assert hi == 40
    assert 1 <= lo < hi <= 100, "band must be a valid non-empty range"


def test_k_hops_is_int_in_range() -> None:
    assert isinstance(config.K_HOPS, int)
    assert 2 <= config.K_HOPS <= 3


def test_tau_is_float_in_open_unit_interval() -> None:
    assert isinstance(config.TAU, float)
    assert 0.0 < config.TAU < 1.0


def test_wdqs_endpoint_is_https_url() -> None:
    assert isinstance(config.WDQS_ENDPOINT, str)
    assert config.WDQS_ENDPOINT.startswith("https://")


def test_qlever_endpoint_is_https_url() -> None:
    assert isinstance(config.QLEVER_ENDPOINT, str)
    assert config.QLEVER_ENDPOINT.startswith("https://")


def test_user_agent_is_non_empty_string() -> None:
    assert isinstance(config.WDQS_USER_AGENT, str)
    assert len(config.WDQS_USER_AGENT) > 0
    # Must mention the project so WDQS can contact the maintainer.
    assert "ivg-kg" in config.WDQS_USER_AGENT


def test_local_llm_model_id_is_non_empty_string() -> None:
    assert isinstance(config.LOCAL_LLM_MODEL_ID, str)
    assert len(config.LOCAL_LLM_MODEL_ID) > 0


def test_minicheck_model_id_is_non_empty_string() -> None:
    assert isinstance(config.MINICHECK_MODEL_ID, str)
    assert len(config.MINICHECK_MODEL_ID) > 0


def test_band_lo_and_hi_match_constants() -> None:
    assert config.SITELINK_BAND == (config.BAND_LO, config.BAND_HI)
