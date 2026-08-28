"""`http.py` のテスト。イベントの解釈、CORS、レスポンス組み立て。"""

from __future__ import annotations

import base64
import json

import pytest
from conftest import ALLOWED_ORIGIN, OTHER_ORIGIN, make_event

from gapatlas.api.errors import InvalidRequestError, MethodNotAllowedError, ScanNotFoundError
from gapatlas.api.http import (
    ALLOW_ORIGIN_HEADER,
    JSON_CONTENT_TYPE,
    build_response,
    cors_headers,
    error_response,
    json_object_body,
    parse_request,
    preflight_response,
)

ALLOWED = [ALLOWED_ORIGIN]

# --- parse_request ----------------------------------------------------------------------


def test_parse_request_reads_method_and_path():
    request = parse_request(make_event("POST", "/api/v1/scans"))

    assert request.method == "POST"
    assert request.path == "/api/v1/scans"


def test_parse_request_uppercases_the_method():
    assert parse_request(make_event("get")).method == "GET"


def test_parse_request_falls_back_to_raw_path():
    event = {"rawPath": "/api/v1/topics", "requestContext": {}}

    assert parse_request(event).path == "/api/v1/topics"


def test_parse_request_lowercases_header_names():
    request = parse_request(make_event(headers={"Origin": ALLOWED_ORIGIN}))

    assert request.headers["origin"] == ALLOWED_ORIGIN
    assert request.origin == ALLOWED_ORIGIN


def test_parse_request_tolerates_null_parameter_maps():
    """API Gateway は該当が無いとき `null` を送る。"""
    event = make_event()
    event["queryStringParameters"] = None
    event["pathParameters"] = None

    request = parse_request(event)

    assert request.query == {}
    assert request.path_parameters == {}


def test_parse_request_reads_path_parameters():
    event = make_event(path="/api/v1/scans/scan_abc123")
    event["pathParameters"] = {"scan_id": "scan_abc123"}

    assert parse_request(event).path_parameters == {"scan_id": "scan_abc123"}


def test_parse_request_reads_the_query_string():
    assert parse_request(make_event(query={"a": "1"})).query == {"a": "1"}


def test_parse_request_decodes_a_base64_body():
    raw = json.dumps({"topic_id": "elder_care"})
    encoded = base64.b64encode(raw.encode()).decode()

    request = parse_request(make_event("POST", body=encoded, is_base64_encoded=True))

    assert request.body == raw


def test_parse_request_rejects_a_broken_base64_body():
    with pytest.raises(InvalidRequestError):
        parse_request(make_event("POST", body="not base64!!", is_base64_encoded=True))


def test_parse_request_returns_none_for_a_missing_body():
    assert parse_request(make_event()).body is None


def test_an_options_request_is_a_preflight():
    assert parse_request(make_event("OPTIONS")).is_preflight


# --- json_object_body -------------------------------------------------------------------


def test_json_object_body_parses_an_object():
    request = parse_request(make_event("POST", body='{"topic_id": "elder_care"}'))

    assert json_object_body(request) == {"topic_id": "elder_care"}


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param("{not json", id="broken json"),
        pytest.param("[1, 2]", id="array"),
        pytest.param('"a string"', id="string"),
        pytest.param("null", id="null"),
    ],
)
def test_json_object_body_rejects_non_objects(body):
    request = parse_request(make_event("POST", body=body))

    with pytest.raises(InvalidRequestError):
        json_object_body(request)


def test_the_json_error_message_does_not_echo_the_body():
    """壊れた本文をそのまま返さない。"""
    request = parse_request(make_event("POST", body='{"secret": "s3cret"'))

    with pytest.raises(InvalidRequestError) as excinfo:
        json_object_body(request)

    assert "s3cret" not in str(excinfo.value)


# --- CORS -------------------------------------------------------------------------------


def test_an_allowed_origin_is_echoed_back():
    headers = cors_headers(ALLOWED_ORIGIN, ALLOWED)

    assert headers[ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN


def test_a_disallowed_origin_gets_no_cors_header():
    assert ALLOW_ORIGIN_HEADER not in cors_headers(OTHER_ORIGIN, ALLOWED)


def test_a_missing_origin_gets_no_cors_header():
    assert ALLOW_ORIGIN_HEADER not in cors_headers(None, ALLOWED)


def test_cors_always_varies_on_origin():
    assert cors_headers(None, ALLOWED)["Vary"] == "Origin"


def test_a_wildcard_setting_never_produces_a_wildcard_header():
    """`CORS_ALLOWED_ORIGINS=*` でもワイルドカードを返さない。"""
    headers = cors_headers(OTHER_ORIGIN, ["*"])

    assert ALLOW_ORIGIN_HEADER not in headers


def test_a_literal_wildcard_origin_is_not_echoed():
    """`Origin: *` を送りつけても `*` を返さない。"""
    assert cors_headers("*", ALLOWED).get(ALLOW_ORIGIN_HEADER) is None


def test_the_origin_match_is_exact():
    assert ALLOW_ORIGIN_HEADER not in cors_headers(f"{ALLOWED_ORIGIN}.evil.example", ALLOWED)


# --- preflight --------------------------------------------------------------------------


def test_a_preflight_from_an_allowed_origin_lists_the_methods():
    response = preflight_response(ALLOWED_ORIGIN, ALLOWED)

    assert response["statusCode"] == 204
    assert response["headers"][ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN
    assert "GET" in response["headers"]["Access-Control-Allow-Methods"]
    assert "POST" in response["headers"]["Access-Control-Allow-Methods"]
    assert response["headers"]["Access-Control-Allow-Headers"] == "Content-Type"
    assert response["body"] == ""


def test_a_preflight_from_a_disallowed_origin_gets_no_cors_headers():
    response = preflight_response(OTHER_ORIGIN, ALLOWED)

    assert response["statusCode"] == 204
    assert ALLOW_ORIGIN_HEADER not in response["headers"]
    assert "Access-Control-Allow-Methods" not in response["headers"]


# --- レスポンス組み立て -----------------------------------------------------------------


def test_build_response_serialises_json():
    response = build_response(200, {"a": 1})

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == JSON_CONTENT_TYPE
    assert json.loads(response["body"]) == {"a": 1}


def test_build_response_keeps_non_ascii_readable():
    response = build_response(200, {"summary": "介護"})

    assert "介護" in response["body"]


def test_error_response_uses_the_documented_envelope():
    response = error_response(ScanNotFoundError())

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["error"]["code"] == "SCAN_NOT_FOUND"


def test_a_method_not_allowed_error_carries_an_allow_header():
    response = error_response(MethodNotAllowedError(("GET",)))

    assert response["statusCode"] == 405
    assert response["headers"]["Allow"] == "GET"
