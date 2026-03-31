import tempfile
import unittest
from pathlib import Path

from tools.adapters.lsl_adapter import LSLStreamAdapter
from tools.adapters.xdf_adapter import XDFStreamAdapter
from tools.matplotlib_views import export_marker_table, visible_marker_events
from tools.stream_types import MarkerEvent, StreamKind, marker_value_from_raw


class ToolsTests(unittest.TestCase):
    class _FakeLSLInfo:
        def __init__(self, *, name: str, stream_type: str, source_id: str) -> None:
            self._name = name
            self._type = stream_type
            self._source_id = source_id

        def name(self) -> str:
            return self._name

        def type(self) -> str:
            return self._type

        def source_id(self) -> str:
            return self._source_id

        def nominal_srate(self) -> float:
            return 0.0

        def channel_count(self) -> int:
            return 1

    class _FakePylslModule:
        def __init__(self, infos) -> None:
            self._infos = infos

        def resolve_streams(self, wait_time: float):
            self.wait_time = wait_time
            return self._infos

    def test_marker_value_from_raw_prefers_event_code(self) -> None:
        value, label, metadata = marker_value_from_raw('{"event_key": "doors.feedback.gain", "event_code": 17}')
        self.assertEqual(value, 17)
        self.assertEqual(label, "doors.feedback.gain")
        self.assertEqual(metadata["event_code"], 17)

    def test_xdf_adapter_lists_streams_and_loads_marker_events(self) -> None:
        fake_streams = [
            {
                "info": {"name": ["PsychoParadigmMarkers"], "type": ["Markers"], "source_id": ["marker-source"], "channel_count": ["1"], "nominal_srate": ["0"]},
                "time_stamps": [100.0, 100.5],
                "time_series": [['{"event_code": 11, "event_key": "doors.fixation.onset"}'], ['{"event_code": 12, "event_key": "doors.choice.onset"}']],
            }
        ]
        adapter = XDFStreamAdapter("demo.xdf", loader=lambda _path: (fake_streams, {"header": 1}))
        descriptors = adapter.list_streams()
        self.assertEqual(descriptors[0].kind, StreamKind.MARKER)
        stream_data = adapter.load_marker_stream(descriptors[0].stream_id)
        self.assertEqual([event.value for event in stream_data.marker_events], [11, 12])
        self.assertEqual(stream_data.marker_events[1].time_s, 0.5)

    def test_lsl_adapter_lists_marker_streams(self) -> None:
        adapter = LSLStreamAdapter(
            pylsl_module=self._FakePylslModule(
                [
                    self._FakeLSLInfo(name="EEG", stream_type="EEG", source_id="eeg-source"),
                    self._FakeLSLInfo(name="PsychoParadigmMarkers", stream_type="Markers", source_id="marker-source"),
                ]
            ),
            resolve_timeout=2.0,
        )
        descriptors = adapter.list_streams()
        self.assertEqual(descriptors[1].kind, StreamKind.MARKER)
        self.assertEqual(descriptors[1].source_id, "marker-source")

    def test_visible_marker_events_filters_by_time_window(self) -> None:
        events = [
            MarkerEvent(index=1, time_s=0.1, value=11, raw_value="11"),
            MarkerEvent(index=2, time_s=0.6, value=12, raw_value="12"),
            MarkerEvent(index=3, time_s=1.2, value=13, raw_value="13"),
        ]
        visible = visible_marker_events(events, 0.5, 1.0)
        self.assertEqual([event.index for event in visible], [2])

    def test_export_marker_table_writes_csv(self) -> None:
        events = [MarkerEvent(index=1, time_s=0.1, value=11, raw_value="11", label="doors.fixation.onset")]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = export_marker_table(events, Path(tmp_dir) / "markers.csv")
            content = path.read_text(encoding="utf-8")
            self.assertIn("doors.fixation.onset", content)
            self.assertIn("0.100000", content)