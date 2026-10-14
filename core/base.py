"""Version-agnostic helpers around pydantic BaseModel."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class Model(BaseModel):
    """Base model that hides the pydantic v1/v2 serialization difference."""

    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()  # type: ignore[attr-defined]
        return self.dict()  # type: ignore[attr-defined]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)  # type: ignore[attr-defined]
        return cls(**data)  # type: ignore[call-arg]
