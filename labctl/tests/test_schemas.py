import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_schemas_are_valid() -> None:
    for path in sorted((ROOT / "benchmarks" / "schema").glob("*.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
