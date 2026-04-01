import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import cv2
import supervision as sv

from counter.line_config import CountLineConfig, load_count_line_config
from counter.stats_export import write_counter_stats
from detection_app import DetectionApp, MODEL_PATH

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class LimeLineCounter:
    def __init__(self, line_config: CountLineConfig, cooldown_frames: int = 12):
        self.line_zone = sv.LineZone(
            start=sv.Point(*line_config.start),
            end=sv.Point(*line_config.end),
            triggering_anchors=(sv.Position.CENTER,),
        )
        self.cooldown_frames = cooldown_frames
        self.frame_index = 0
        self.smoothed_in_count = 0
        self.smoothed_out_count = 0
        self.last_counted_frame_by_id: dict[int, int] = {}

        self.line_zone_annotator = sv.LineZoneAnnotator(
            thickness=3,
            text_scale=0.8,
            text_thickness=2,
            text_padding=10,
            display_in_count=False,
            display_out_count=False,
            display_text_box=False,
        )

    def apply(self, prediction, video_frame) -> None:
        self.frame_index += 1

        if prediction.tracker_id is None:
            logging.warning("Line counter requires tracker IDs. Enable tracking.")
            self._annotate_overlay(video_frame.image)
            return

        in_mask, out_mask = self.line_zone.trigger(prediction)
        in_inc, out_inc = self._count_smoothed_crossings(
            tracker_ids=prediction.tracker_id,
            in_mask=in_mask,
            out_mask=out_mask,
        )

        self.smoothed_in_count += in_inc
        self.smoothed_out_count += out_inc
        self._annotate_overlay(video_frame.image)

    def _count_smoothed_crossings(self, tracker_ids, in_mask, out_mask) -> tuple[int, int]:
        in_increment = 0
        out_increment = 0

        for idx, track_id_value in enumerate(tracker_ids):
            if not in_mask[idx] and not out_mask[idx]:
                continue

            if track_id_value is None:
                continue

            tracker_id = int(track_id_value)
            last_counted_frame = self.last_counted_frame_by_id.get(tracker_id)
            if (
                last_counted_frame is not None
                and self.frame_index - last_counted_frame <= self.cooldown_frames
            ):
                continue

            if in_mask[idx] and not out_mask[idx]:
                in_increment += 1
                self.last_counted_frame_by_id[tracker_id] = self.frame_index
                continue

            if out_mask[idx] and not in_mask[idx]:
                out_increment += 1
                self.last_counted_frame_by_id[tracker_id] = self.frame_index

        return in_increment, out_increment

    def _annotate_overlay(self, frame) -> None:
        self.line_zone_annotator.annotate(frame=frame, line_counter=self.line_zone)

        total = self.total_count
        overlay_text = (
            f"Total: {total}  |  IN: {self.smoothed_in_count}  |  OUT: {self.smoothed_out_count}"
        )

        cv2.rectangle(frame, (10, 10), (520, 52), (0, 0, 0), -1)
        cv2.putText(
            frame,
            overlay_text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (80, 255, 80),
            2,
            cv2.LINE_AA,
        )

    @property
    def total_count(self) -> int:
        return self.smoothed_in_count + self.smoothed_out_count


class ShowcaseDetectionApp(DetectionApp):
    def __init__(
        self,
        weights_path: str,
        video_source: str,
        show: bool,
        save: bool,
        output_path: str,
        line_config_path: str,
        cooldown_frames: int,
    ):
        super().__init__(
            weights_path=weights_path,
            video_source=video_source,
            show=show,
            save=save,
            output_path=output_path,
            track=True,
        )
        self.started_at = datetime.now(timezone.utc)
        self.processed_frames = 0
        self.line_config_path = line_config_path
        self.line_config = load_count_line_config(line_config_path)
        self.counter = LimeLineCounter(
            line_config=self.line_config,
            cooldown_frames=cooldown_frames,
        )

    def process_predicted_frame(self, prediction, video_frame):
        self.processed_frames += 1
        self.counter.apply(prediction=prediction, video_frame=video_frame)
        return prediction

    def build_stats_payload(self, output_video_path: str | None = None) -> dict:
        finished_at = datetime.now(timezone.utc)
        duration_seconds = (finished_at - self.started_at).total_seconds()

        payload = {
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(duration_seconds, 3),
            "source": str(self.video_source),
            "line_config_path": self.line_config_path,
            "line": {
                "start": [self.line_config.start[0], self.line_config.start[1]],
                "end": [self.line_config.end[0], self.line_config.end[1]],
            },
            "frames_processed": self.processed_frames,
            "cooldown_frames": self.counter.cooldown_frames,
            "counts": {
                "in": self.counter.smoothed_in_count,
                "out": self.counter.smoothed_out_count,
                "total": self.counter.total_count,
            },
        }

        if output_video_path:
            payload["output_video_path"] = output_video_path

        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Showcase lime counter with line trigger.")
    parser.add_argument("--source", type=str, default="example_media/lime_1.mp4")
    parser.add_argument("--weights", type=str, default=MODEL_PATH)
    parser.add_argument("--line-config", type=str, default="output/count_line.json")
    parser.add_argument("--output", type=str, default="output/showcase_counted.mp4")
    parser.add_argument("--stats-output", type=str, default="output/showcase_stats.json")
    parser.add_argument(
        "--cooldown-frames",
        type=int,
        default=12,
        help="Minimum frame gap before the same tracker can be counted again.",
    )

    parser.add_argument("--show", action="store_true", default=False)
    parser.add_argument("--save", action="store_true", default=False)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.show and not args.save:
        raise ValueError("Enable at least one output mode: --show and/or --save")

    if args.save:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    app = ShowcaseDetectionApp(
        weights_path=args.weights,
        video_source=args.source,
        show=args.show,
        save=args.save,
        output_path=args.output,
        line_config_path=args.line_config,
        cooldown_frames=args.cooldown_frames,
    )
    app.run()

    stats_payload = app.build_stats_payload(output_video_path=args.output if args.save else None)
    write_counter_stats(path=args.stats_output, payload=stats_payload)
    logging.info("Saved run stats to %s", args.stats_output)


if __name__ == "__main__":
    main()
