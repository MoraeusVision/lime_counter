import argparse
import logging
from datetime import datetime, timezone

import cv2

from counter.line_config import CountLineConfig, save_count_line_config
from utils import parse_video_source

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class LineSelectorApp:
    def __init__(self, source: str, output_path: str):
        self.source = parse_video_source(source)
        self.output_path = output_path

        self.start: tuple[int, int] | None = None
        self.end: tuple[int, int] | None = None
        self.is_drawing = False

        self.window_name = "Line Selector"

    def run(self) -> None:
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open source: {self.source}")

        ok, first_frame = cap.read()
        cap.release()

        if not ok or first_frame is None:
            raise RuntimeError("Could not read first frame from source.")

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.on_mouse)

        while True:
            frame = first_frame.copy()
            self.draw_overlay(frame)
            cv2.imshow(self.window_name, frame)

            key = cv2.waitKey(16) & 0xFF
            if key == ord("q"):
                logging.info("Quit without saving line config.")
                break
            if key == ord("r"):
                self.start = None
                self.end = None
                self.is_drawing = False
                logging.info("Reset line.")
            if key == ord("s"):
                if self.start is None or self.end is None:
                    logging.warning("Draw a line first before saving.")
                    continue

                self.save_config(frame_width=first_frame.shape[1], frame_height=first_frame.shape[0])
                logging.info(f"Saved line config to {self.output_path}")
                break

        cv2.destroyAllWindows()

    def on_mouse(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.start = (x, y)
            self.end = (x, y)
            self.is_drawing = True
            return

        if event == cv2.EVENT_MOUSEMOVE and self.is_drawing:
            self.end = (x, y)
            return

        if event == cv2.EVENT_LBUTTONUP and self.is_drawing:
            self.end = (x, y)
            self.is_drawing = False

    def draw_overlay(self, frame) -> None:
        if self.start is not None and self.end is not None:
            cv2.line(frame, self.start, self.end, (0, 255, 255), 3)

        instructions = "Draw line with mouse | s: save | r: reset | q: quit"
        cv2.rectangle(frame, (10, 10), (620, 45), (0, 0, 0), -1)
        cv2.putText(
            frame,
            instructions,
            (20, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def save_config(self, frame_width: int, frame_height: int) -> None:
        if self.start is None or self.end is None:
            raise RuntimeError("Cannot save config without a line.")

        config = CountLineConfig(start=self.start, end=self.end)
        save_count_line_config(
            path=self.output_path,
            config=config,
            extra={
                "source": str(self.source),
                "frame_size": [frame_width, frame_height],
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draw and save counting line from first frame.")
    parser.add_argument("--source", type=str, default="example_media/lime_1.mp4")
    parser.add_argument("--output", type=str, default="output/count_line.json")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = LineSelectorApp(source=args.source, output_path=args.output)
    app.run()
