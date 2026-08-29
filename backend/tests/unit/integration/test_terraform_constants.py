"""Terraform と backend の定数が一致していることを固定する。

`infrastructure/README.md` は「片方だけ変えると壊れる」定数を一覧している。
コメントで紐付けてはいるが**機械的な検証が無い**ため、Terraform 側だけを
変えても Python のテストは何も落ちなかった(W7 の第三者指摘)。

このテストは `.tf` を正規表現で読む。Terraform の構文解析はしない
(依存を増やさないため)。**該当行が見つからない場合は失敗させる** ことで、
リファクタで紐付けが切れたことに気付けるようにする。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gapatlas.adapters.dynamodb.table import (
    PARTITION_KEY_ATTRIBUTE,
    SORT_KEY_ATTRIBUTE,
    TTL_ATTRIBUTE,
)
from gapatlas.adapters.s3.keys import CURATED_DATASET, CURATED_PREFIX, DATE_FORMAT
from gapatlas.api import lambda_handlers, worker_handler

TERRAFORM_DIR = Path(__file__).resolve().parents[3].parent / "infrastructure" / "terraform"


def _read(name: str) -> str:
    path = TERRAFORM_DIR / name
    if not path.is_file():
        pytest.skip(f"terraform ファイルが無い: {path}")
    return path.read_text(encoding="utf-8")


def _single(pattern: str, text: str, *, what: str) -> str:
    matches = re.findall(pattern, text)
    assert matches, f"{what} が見つからない(紐付けが切れている可能性)"
    return matches[0]


def test_dynamodb_key_attributes_match():
    """`hash_key` / `range_key` / `ttl` が `table.py` と一致すること。"""
    text = _read("dynamodb.tf")
    assert _single(r'hash_key\s*=\s*"([^"]+)"', text, what="hash_key") == PARTITION_KEY_ATTRIBUTE
    assert _single(r'range_key\s*=\s*"([^"]+)"', text, what="range_key") == SORT_KEY_ATTRIBUTE
    assert (
        _single(r'attribute_name\s*=\s*"([^"]+)"', text, what="ttl attribute_name") == TTL_ATTRIBUTE
    )


def test_glue_partition_columns_match_the_s3_key_layout():
    """Glue のパーティション列が `keys.py` の配置と一致すること。

    `curated/gap_scores/topic=.../country=.../dt=.../` の順。
    """
    text = _read("glue.tf")
    partitions = re.findall(r"partition_keys\s*\{\s*name\s*=\s*\"([^\"]+)\"", text)
    assert partitions == ["topic", "country", "dt"]


def test_the_glue_table_location_matches_the_curated_prefix():
    text = _read("main.tf") + _read("glue.tf")
    assert f"{CURATED_PREFIX}/{CURATED_DATASET}" in text


def test_the_partition_date_format_is_iso_like():
    """`dt=YYYY-MM-DD`。Glue の射影(`date` 形式)と揃っていること。"""
    assert DATE_FORMAT == "%Y-%m-%d"
    text = _read("glue.tf")
    assert "yyyy-MM-dd" in text


def test_lambda_handlers_exist():
    """Terraform が指すハンドラが実際に存在すること。"""
    text = _read("lambda.tf")
    handlers = re.findall(r'handler\s*=\s*"([^"]+)"', text)
    assert "gapatlas.api.lambda_handlers.api_handler" in handlers
    assert "gapatlas.api.worker_handler.worker_handler" in handlers
    assert callable(lambda_handlers.api_handler)
    assert callable(worker_handler.worker_handler)


def test_the_worker_event_source_uses_a_batch_size_of_one():
    """`adapters/sqs/decode.py` は `batchSize = 1` を前提にしている。"""
    text = _read("lambda.tf")
    assert _single(r"batch_size\s*=\s*(\d+)", text, what="batch_size") == "1"


def test_the_query_profiles_dir_is_passed_to_lambda():
    """省略すると全国が無言で FAILED になる(W7 の第三者指摘)。"""
    text = _read("lambda.tf")
    assert "QUERY_PROFILES_DIR" in text


def test_the_athena_workgroup_is_passed_to_lambda():
    """backend の既定値と Terraform の名前が食い違うとクエリが必ず失敗する。"""
    text = _read("lambda.tf")
    assert "ATHENA_WORKGROUP" in text
