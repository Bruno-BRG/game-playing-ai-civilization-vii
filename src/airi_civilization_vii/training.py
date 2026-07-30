"""YOLO26 training and export entrypoints."""

from __future__ import annotations

from pathlib import Path


def train_yolo26(
    *,
    data: Path,
    model: str,
    epochs: int,
    image_size: int,
    output_directory: Path,
) -> None:
    """Fine-tune a YOLO26 detection model on the Civilization VII dataset."""

    if not data.exists():
        raise FileNotFoundError(data)
    if epochs < 1:
        raise ValueError("epochs must be positive")

    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeError("Install YOLO support with: uv sync --extra vision") from error

    detector = YOLO(model)
    detector.train(
        data=str(data),
        epochs=epochs,
        imgsz=image_size,
        project=str(output_directory),
        name="yolo26n-civilization-vii",
    )


def export_onnx(*, model_path: Path, image_size: int, output_directory: Path) -> Path:
    """Export a trained YOLO26 model using its end-to-end, NMS-free head."""

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeError("Install YOLO support with: uv sync --extra vision") from error

    output_directory.mkdir(parents=True, exist_ok=True)
    detector = YOLO(str(model_path))
    exported = detector.export(format="onnx", imgsz=image_size, end2end=True)
    exported_path = Path(exported)
    destination = output_directory / exported_path.name
    if exported_path.resolve() != destination.resolve():
        exported_path.replace(destination)
    return destination
