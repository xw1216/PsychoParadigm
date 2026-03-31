from __future__ import annotations

import csv
from pathlib import Path

from tools.adapters.lsl_adapter import LSLMarkerSubscription
from tools.stream_types import MarkerEvent, UnifiedStreamData, marker_value_text


def visible_marker_events(events: list[MarkerEvent], xmin: float, xmax: float) -> list[MarkerEvent]:
    return [event for event in events if xmin <= event.time_s <= xmax]


def export_marker_table(events: list[MarkerEvent], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "time_s", "marker", "label", "raw_value"])
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "index": event.index,
                    "time_s": f"{event.time_s:.6f}",
                    "marker": marker_value_text(event),
                    "label": event.label or "",
                    "raw_value": event.raw_value,
                }
            )
    return path


class MarkerTimelineViewer:
    def __init__(self, stream_data: UnifiedStreamData, *, export_path: str | Path | None = None) -> None:
        import matplotlib.pyplot as plt

        self.plt = plt
        self.stream_data = stream_data
        self.export_path = Path(export_path) if export_path is not None else None
        self.selected_event_index: int | None = 0 if stream_data.marker_events else None

        self.figure, (self.axis_timeline, self.axis_table) = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            gridspec_kw={"height_ratios": [3, 2]},
        )
        self.axis_table.axis("off")
        self._scatter = None
        self._status_text = self.figure.text(0.01, 0.98, "", ha="left", va="top")
        self.figure.canvas.mpl_connect("button_press_event", self._on_click)
        self.figure.canvas.mpl_connect("key_press_event", self._on_key_press)

    def show(self) -> None:
        self._draw()
        self.plt.show()

    def _draw(self) -> None:
        events = self.stream_data.marker_events
        self.axis_timeline.clear()
        self.axis_table.clear()
        self.axis_table.axis("off")
        self.axis_timeline.set_title(f"{self.stream_data.descriptor.name} | marker 轨")
        self.axis_timeline.set_xlabel("共享时间轴（秒）")
        self.axis_timeline.set_yticks([1.0])
        self.axis_timeline.set_yticklabels(["marker"])
        self.axis_timeline.grid(axis="x", alpha=0.25)

        if not events:
            self._status_text.set_text("当前 stream 中没有 marker 事件。")
            self.axis_table.text(0.0, 1.0, "没有可显示的 marker。", va="top", family="monospace")
            self.figure.tight_layout()
            return

        times = [event.time_s for event in events]
        values = [marker_value_text(event) for event in events]
        self.axis_timeline.vlines(times, 0.75, 1.25, color="#1f77b4", linewidth=1.0)
        self._scatter = self.axis_timeline.scatter(times, [1.0] * len(times), s=32, color="#1f77b4", picker=True)
        for event in events:
            self.axis_timeline.text(event.time_s, 1.04, marker_value_text(event), rotation=30, fontsize=8, ha="left", va="bottom")

        if len(times) == 1:
            self.axis_timeline.set_xlim(max(0.0, times[0] - 1.0), times[0] + 1.0)

        selected = events[self.selected_event_index] if self.selected_event_index is not None else None
        if selected is not None:
            self.axis_timeline.axvline(selected.time_s, color="#d62728", linestyle="--", linewidth=1.2)

        visible = self.current_visible_events()
        table_lines = ["index   time(s)   marker   label"]
        for event in visible[:20]:
            marker = marker_value_text(event)
            label = event.label or ""
            prefix = ">" if selected is not None and event.index == selected.index else " "
            table_lines.append(f"{prefix}{event.index:04d}   {event.time_s:7.3f}   {marker:>6}   {label}")
        self.axis_table.text(0.0, 1.0, "\n".join(table_lines), va="top", family="monospace")

        selected_text = "无"
        if selected is not None:
            selected_text = f"#{selected.index} @ {selected.time_s:.3f}s marker={marker_value_text(selected)}"
        self._status_text.set_text(
            f"总 marker 数: {len(events)} | 当前可见: {len(visible)} | 已选中: {selected_text} | 按 e 导出当前可见 marker 表"
        )
        self.figure.tight_layout(rect=(0, 0, 1, 0.95))

    def current_visible_events(self) -> list[MarkerEvent]:
        xmin, xmax = self.axis_timeline.get_xlim()
        return visible_marker_events(self.stream_data.marker_events, xmin, xmax)

    def export_visible(self) -> Path:
        if self.export_path is None:
            stem = self.stream_data.descriptor.name.replace(" ", "_")
            self.export_path = Path.cwd() / f"{stem}_markers.csv"
        path = export_marker_table(self.current_visible_events(), self.export_path)
        print(f"已导出 marker 表: {path}")
        return path

    def _on_key_press(self, event) -> None:
        if event.key == "e":
            self.export_visible()
        elif event.key in {"left", "right"} and self.stream_data.marker_events:
            step = -1 if event.key == "left" else 1
            if self.selected_event_index is None:
                self.selected_event_index = 0
            else:
                self.selected_event_index = max(0, min(len(self.stream_data.marker_events) - 1, self.selected_event_index + step))
            self._center_on_selected()
            self._draw()
            self.figure.canvas.draw_idle()

    def _on_click(self, event) -> None:
        if event.inaxes != self.axis_timeline or event.xdata is None or not self.stream_data.marker_events:
            return
        nearest_index = min(
            range(len(self.stream_data.marker_events)),
            key=lambda idx: abs(self.stream_data.marker_events[idx].time_s - float(event.xdata)),
        )
        self.selected_event_index = nearest_index
        self._center_on_selected()
        self._draw()
        self.figure.canvas.draw_idle()

    def _center_on_selected(self) -> None:
        if self.selected_event_index is None:
            return
        selected = self.stream_data.marker_events[self.selected_event_index]
        xmin, xmax = self.axis_timeline.get_xlim()
        window = max(2.0, xmax - xmin)
        half_window = window / 2.0
        self.axis_timeline.set_xlim(max(0.0, selected.time_s - half_window), selected.time_s + half_window)


class LiveMarkerMonitor:
    def __init__(
        self,
        subscription: LSLMarkerSubscription,
        *,
        window_seconds: float = 20.0,
        max_events: int = 200,
        refresh_ms: int = 200,
    ) -> None:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
        from matplotlib.widgets import Button

        self.plt = plt
        self.FuncAnimation = FuncAnimation
        self.Button = Button
        self.subscription = subscription
        self.window_seconds = window_seconds
        self.max_events = max_events
        self.refresh_ms = refresh_ms
        self.running = True
        self.events: list[MarkerEvent] = []

        self.figure, (self.axis_timeline, self.axis_table) = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            gridspec_kw={"height_ratios": [3, 2]},
        )
        self.axis_table.axis("off")
        self.figure.subplots_adjust(bottom=0.14, top=0.9)
        self.status_text = self.figure.text(0.01, 0.98, "", ha="left", va="top")
        start_axis = self.figure.add_axes([0.72, 0.02, 0.1, 0.05])
        stop_axis = self.figure.add_axes([0.84, 0.02, 0.1, 0.05])
        self.start_button = Button(start_axis, "Start")
        self.stop_button = Button(stop_axis, "Stop")
        self.start_button.on_clicked(lambda _event: self._set_running(True))
        self.stop_button.on_clicked(lambda _event: self._set_running(False))
        self.figure.canvas.mpl_connect("key_press_event", self._on_key_press)
        self.animation = self.FuncAnimation(self.figure, self._update, interval=self.refresh_ms, cache_frame_data=False)
        self.figure._animation_ref = self.animation

    def show(self) -> None:
        self.plt.show()

    def _set_running(self, state: bool) -> None:
        self.running = state
        self._draw()
        self.figure.canvas.draw_idle()

    def _on_key_press(self, event) -> None:
        if event.key == " ":
            self._set_running(not self.running)

    def _update(self, _frame_index: int) -> None:
        if self.running:
            new_events = self.subscription.pull(timeout=0.0)
            if new_events:
                self.events.extend(new_events)
                if len(self.events) > self.max_events:
                    self.events = self.events[-self.max_events :]
        self._draw()

    def _draw(self) -> None:
        self.axis_timeline.clear()
        self.axis_table.clear()
        self.axis_table.axis("off")
        self.axis_timeline.set_title(f"{self.subscription.descriptor.name} | 实时 marker 监视")
        self.axis_timeline.set_xlabel("共享时间轴（秒）")
        self.axis_timeline.set_yticks([1.0])
        self.axis_timeline.set_yticklabels(["marker"])
        self.axis_timeline.grid(axis="x", alpha=0.25)

        if not self.events:
            latest_text = "暂无 marker"
            latest_time = "-"
            self.axis_table.text(0.0, 1.0, "尚未收到 marker。\n点击 Start 或按空格开始监视。", va="top", family="monospace")
        else:
            latest = self.events[-1]
            latest_text = marker_value_text(latest)
            latest_time = f"{latest.time_s:.3f}s"
            latest_time_s = latest.time_s
            window_start = max(0.0, latest_time_s - self.window_seconds)
            visible = [event for event in self.events if event.time_s >= window_start]
            times = [event.time_s for event in visible]
            self.axis_timeline.vlines(times, 0.75, 1.25, color="#1f77b4", linewidth=1.0)
            self.axis_timeline.scatter(times, [1.0] * len(times), s=32, color="#1f77b4")
            for event in visible:
                self.axis_timeline.text(event.time_s, 1.04, marker_value_text(event), rotation=30, fontsize=8, ha="left", va="bottom")
            self.axis_timeline.set_xlim(window_start, max(window_start + self.window_seconds, latest_time_s + 0.5))
            lines = ["index   time(s)   marker   label"]
            for event in visible[-15:]:
                lines.append(f"{event.index:04d}   {event.time_s:7.3f}   {marker_value_text(event):>6}   {event.label or ''}")
            self.axis_table.text(0.0, 1.0, "\n".join(lines), va="top", family="monospace")

        state = "运行中" if self.running else "已停止"
        source_id = self.subscription.descriptor.source_id or "-"
        self.status_text.set_text(
            f"状态: {state} | stream={self.subscription.descriptor.name} | source_id={source_id} | 最新 marker={latest_text} | 最新时间={latest_time}"
        )
