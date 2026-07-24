from pathlib import Path

import pytest
from PIL import Image

from app.validation import validate_reference_image
from pipeline.errors import PipelineError


def test_small_reference_image_is_rejected(tmp_path: Path) -> None:
    image_path = tmp_path / "small.png"
    Image.new("RGB", (500, 600)).save(image_path)
    with pytest.raises(PipelineError, match="512px"):
        validate_reference_image(image_path, "basic")


def test_sufficiently_large_reference_image_passes_basic_validation(tmp_path: Path) -> None:
    image_path = tmp_path / "portrait.png"
    Image.new("RGB", (768, 768)).save(image_path)
    validate_reference_image(image_path, "basic")

