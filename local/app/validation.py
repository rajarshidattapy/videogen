from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from pipeline.errors import PipelineError


def validate_reference_image(image_path: Path, face_validation: str) -> None:
    try:
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise PipelineError("The upload is not a readable image.") from exc

    if min(width, height) < 512:
        raise PipelineError(
            f"Image is {width}x{height}; use a sharp, well-lit image with at least 512px on each side."
        )
    if face_validation not in {"insightface", "required"}:
        return

    try:
        import cv2
        from insightface.app import FaceAnalysis
    except ImportError as exc:
        raise PipelineError(
            "FACE_VALIDATION=insightface requires the optional face-validation dependencies. "
            "Install this project's [face-validation] extra or set FACE_VALIDATION=basic."
        ) from exc

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    faces = app.get(cv2.imread(str(image_path)))
    if len(faces) == 0:
        raise PipelineError("No face detected. Use a clear, front-facing portrait.")
    if len(faces) > 1:
        raise PipelineError("Multiple faces detected. Upload an image containing one person only.")
    face = faces[0]
    face_width = face.bbox[2] - face.bbox[0]
    if face_width < 256:
        raise PipelineError(f"Face is too small ({int(face_width)}px); use a closer portrait (256px+ face).")
    pose = getattr(face, "pose", None)
    if pose is not None and len(pose) > 1 and abs(float(pose[1])) > 20:
        raise PipelineError("Head is turned too far from camera. Use a frontal portrait.")

