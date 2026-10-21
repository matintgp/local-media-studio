"""Optional future prompt assistance. No provider credentials or network by default.

Providers return text/validated plans. They never execute tools directly: an
accepted plan must enter the same application workflow and admission scheduler.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PromptRequest:
    text: str
    language: str
    modality: str


class PromptProvider(Protocol):
    async def suggest(self, request: PromptRequest) -> str: ...


class ProviderDisabled:
    async def suggest(self, request: PromptRequest) -> str:
        raise RuntimeError('Prompt assistance is not enabled; manual workflows remain available')
