"""Shared pydantic configuration for SDK game models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StateModel(BaseModel):
    """Forward-compatible bot-visible state model."""

    model_config = ConfigDict(extra="allow")


class ActionModel(BaseModel):
    """Strict action model; malformed actions should fail before submission."""

    model_config = ConfigDict(extra="forbid")
