"""Object-detection adapters for Civilization VII frames."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from PIL import Image

from .domain import BoundingBox, Detection


class Detector(Protocol):
    """Maps an RGB frame to semantic UI and game entities."""

    def detect(self, image: Image.Image) -> tuple[Detection, ...]: ...


class NullDetector:
    """Allow capture and trace validation before a trained model exists."""

    def detect(self, image: Image.Image) -> tuple[Detection, ...]:
        del image
        return ()


class YoloDetector:
    """Run a custom Ultralytics YOLO26 detection model.

    The model is imported lazily so dataset and orchestration tests do not require
    PyTorch. Class names come from the training dataset and become planner labels.
    """

    def __init__(self, model_path: Path, *, confidence: float = 0.4, image_size: int = 960) -> None:
        if not model_path.exists():
            raise FileNotFoundError(model_path)
        if not 0 < confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("Install YOLO support with: uv sync --extra vision") from error

        self._model = YOLO(str(model_path))
        self._confidence = confidence
        self._image_size = image_size

    def detect(self, image: Image.Image) -> tuple[Detection, ...]:
        results = self._model.predict(
            source=image,
            conf=self._confidence,
            imgsz=self._image_size,
            verbose=False,
        )
        if not results:
            return ()

        result = results[0]
        boxes = result.boxes
        if boxes is None:
            return ()

        labels: Sequence[str] | dict[int, str] = result.names
        occurrences: dict[str, int] = {}
        detections: list[Detection] = []
        for coordinates, confidence, class_index in zip(
            boxes.xyxy.cpu().tolist(),
            boxes.conf.cpu().tolist(),
            boxes.cls.cpu().tolist(),
            strict=True,
        ):
            label = labels[int(class_index)]
            occurrence = occurrences.get(label, 0)
            occurrences[label] = occurrence + 1
            left, top, right, bottom = (round(value) for value in coordinates)
            clamped_left = min(image.width - 1, max(0, left))
            clamped_top = min(image.height - 1, max(0, top))
            detections.append(
                Detection(
                    id=f"{label}:{occurrence}",
                    label=label,
                    confidence=float(confidence),
                    box=BoundingBox(
                        left=clamped_left,
                        top=clamped_top,
                        right=min(image.width, max(clamped_left + 1, right)),
                        bottom=min(image.height, max(clamped_top + 1, bottom)),
                    ),
                )
            )
        return tuple(detections)
