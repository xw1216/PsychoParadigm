from __future__ import annotations

from abc import ABC, abstractmethod

from ..stream_types import StreamDescriptor, UnifiedStreamData


class BaseStreamAdapter(ABC):
    @abstractmethod
    def list_streams(self) -> list[StreamDescriptor]:
        raise NotImplementedError

    @abstractmethod
    def load_marker_stream(self, stream_id: str) -> UnifiedStreamData:
        raise NotImplementedError
