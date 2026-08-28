"""QueryProfile(国別クエリ定義 YAML)のローダー。

ファイル配置: `<base_dir>/<topic_id>/<COUNTRY>.yaml`
既定の `base_dir` はリポジトリルートの `config/query_profiles`。
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from gapatlas.config.errors import QueryProfileNotFoundError, QueryProfileValidationError
from gapatlas.domain.models.common import Country, TopicId
from gapatlas.domain.models.query_profile import QueryProfile

_MODULE_PATH: Final[Path] = Path(__file__).resolve()

# _MODULE_PATH = <repo>/backend/src/gapatlas/config/query_profile_loader.py
#   parents[0] = <repo>/backend/src/gapatlas/config
#   parents[1] = <repo>/backend/src/gapatlas
#   parents[2] = <repo>/backend/src
#   parents[3] = <repo>/backend
#   parents[4] = <repo>            ← リポジトリルート
_REPO_ROOT: Final[Path] = _MODULE_PATH.parents[4]

DEFAULT_QUERY_PROFILES_DIR: Final[Path] = _REPO_ROOT / "config" / "query_profiles"
"""既定のプロファイル格納ディレクトリ。"""

PROFILE_SUFFIX: Final[str] = ".yaml"


def _resolve_base_dir(base_dir: Path | None) -> Path:
    return (base_dir or DEFAULT_QUERY_PROFILES_DIR).resolve()


def _profile_path(topic_id: TopicId, country: Country, base_dir: Path) -> Path:
    """プロファイルのパスを組み立て、`base_dir` の外を指さないことを保証する。

    `topic_id` / `country` は Enum のため任意文字列は入らないが、`base_dir` 自体が
    シンボリックリンク等を含む場合に備え、解決後のパスを再確認する。
    """
    candidate = (base_dir / topic_id.value / f"{country.value}{PROFILE_SUFFIX}").resolve()
    if not candidate.is_relative_to(base_dir):
        message = f"resolved query profile path escapes base_dir: topic_id={topic_id.value}"
        raise QueryProfileValidationError(message)
    return candidate


def load_query_profile(
    topic_id: TopicId, country: Country, base_dir: Path | None = None
) -> QueryProfile:
    """1件の QueryProfile を読み込む。

    Args:
        topic_id: トピック。
        country: 国。ファイル名(`<COUNTRY>.yaml`)と YAML の `country` の両方に一致すること。
        base_dir: プロファイル格納ディレクトリ。省略時はリポジトリルートの
            `config/query_profiles`。

    Raises:
        QueryProfileNotFoundError: 該当ファイルが存在しない場合。
        QueryProfileValidationError: YAML の形式または内容が不正な場合。
    """
    resolved_base = _resolve_base_dir(base_dir)
    path = _profile_path(topic_id, country, resolved_base)

    if not path.is_file():
        message = (
            f"query profile not found: topic_id={topic_id.value}, "
            f"country={country.value}, path={path}"
        )
        raise QueryProfileNotFoundError(message)

    raw = _load_yaml_mapping(path)
    profile = _build_profile(raw, path)

    if profile.country is not country:
        message = (
            f"country mismatch: file name says '{country.value}' "
            f"but YAML 'country' is '{profile.country.value}' (path={path})"
        )
        raise QueryProfileValidationError(message)
    # MVP の TopicId は1要素のみ。Enum 同士の比較では型チェッカが常に真と判断して
    # しまうため、値同士を比較して将来のトピック追加にも耐えられるようにする。
    if profile.topic_id.value != topic_id.value:
        message = (
            f"topic_id mismatch: directory says '{topic_id.value}' "
            f"but YAML 'topic_id' is '{profile.topic_id.value}' (path={path})"
        )
        raise QueryProfileValidationError(message)

    return profile


def load_all_query_profiles(
    topic_id: TopicId, base_dir: Path | None = None
) -> dict[Country, QueryProfile]:
    """`Country` に定義されたすべての国のプロファイルを読み込む。

    1件でも欠けていれば `QueryProfileNotFoundError` を送出する。
    起動時に不備を検出するための挙動(docs/query-profiles.md)。
    """
    return {country: load_query_profile(topic_id, country, base_dir) for country in Country}


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    """YAML をマッピングとして読み込む。`yaml.safe_load` のみ使用する。"""
    text = path.read_text(encoding="utf-8")
    try:
        loaded: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        message = f"failed to parse query profile YAML: path={path}"
        raise QueryProfileValidationError(message) from exc

    if not isinstance(loaded, dict):
        message = f"query profile must be a YAML mapping: path={path}"
        raise QueryProfileValidationError(message)

    invalid_keys = [key for key in loaded if not isinstance(key, str)]
    if invalid_keys:
        message = f"query profile keys must be strings: path={path}"
        raise QueryProfileValidationError(message)

    return {str(key): value for key, value in loaded.items()}


def _build_profile(raw: dict[str, object], path: Path) -> QueryProfile:
    try:
        return QueryProfile.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        message = f"invalid query profile: path={path}: {details}"
        raise QueryProfileValidationError(message) from exc
