"""Labeled evaluation records."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter


class EvalRecord(BaseModel):
    """A null expected_entity_id means rejecting the input (unknown) is correct."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: str
    expected_entity_id: str | None
    case_type: str


_DATASET = TypeAdapter(list[EvalRecord])


def load_dataset(path: Path) -> list[EvalRecord]:
    return _DATASET.validate_json(path.read_bytes())
