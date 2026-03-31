from __future__ import annotations

from pydantic import BaseModel, Field


class CompareDimensionDiff(BaseModel):
    dimension_group: str
    dimension_key: str
    score_a: float | None = None
    score_b: float | None = None
    diff: float | None = None


class CompareDirectivesResponse(BaseModel):
    directive_id_a: str
    directive_id_b: str
    dimension_model_id: str
    dimensions: list[CompareDimensionDiff]
    embedding_cosine_distance: float | None = None
    embedding_model: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "directive_id_a": "00000000-0000-0000-0000-000000000001",
                    "directive_id_b": "00000000-0000-0000-0000-000000000002",
                    "dimension_model_id": "00000000-0000-0000-0000-0000000000aa",
                    "dimensions": [
                        {
                            "dimension_group": "quality",
                            "dimension_key": "skillness",
                            "score_a": 0.5,
                            "score_b": 0.7,
                            "diff": 0.2,
                        }
                    ],
                    "embedding_cosine_distance": 0.12,
                    "embedding_model": "text-embedding-3-small",
                }
            ],
        }
    }


class ClusterGroupResponse(BaseModel):
    cluster_id: int
    directive_ids: list[str]
    member_count: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cluster_id": 0,
                    "directive_ids": ["00000000-0000-0000-0000-000000000001"],
                    "member_count": 1,
                }
            ],
        }
    }


class RecommendSimilarItem(BaseModel):
    directive_id: str
    cosine_distance: float = Field(examples=[0.15])

    model_config = {
        "json_schema_extra": {
            "examples": [{"directive_id": "00000000-0000-0000-0000-000000000002", "cosine_distance": 0.21}],
        }
    }


class DirectiveExplainResponse(BaseModel):
    directive_id: str
    dimension_model_id: str
    explanation: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "directive_id": "00000000-0000-0000-0000-000000000001",
                    "dimension_model_id": "00000000-0000-0000-0000-0000000000aa",
                    "explanation": "Profile summary: 34 dimension(s) scored; mean 0.55 on a 0–1 scale.",
                }
            ],
        }
    }
