"""OCR wrappers for desktop screenshot analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class OCRLine:
    text: str
    score: float
    points: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]

    @property
    def x1(self) -> float:
        return min(point[0] for point in self.points)

    @property
    def x2(self) -> float:
        return max(point[0] for point in self.points)

    @property
    def y1(self) -> float:
        return min(point[1] for point in self.points)

    @property
    def y2(self) -> float:
        return max(point[1] for point in self.points)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


class RapidOcrReader:
    """Run OCR on a screenshot and normalize the result into OCRLine entries."""

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:
            raise RuntimeError(
                "rapidocr-onnxruntime is required for vision-based WeChat reading. "
                "Install it with `pip install rapidocr-onnxruntime`."
            ) from error

        self._engine = RapidOCR()

    def read(self, image: np.ndarray | Path | str) -> list[OCRLine]:
        result, _ = self._engine(image)
        if not result:
            return []

        lines: list[OCRLine] = []
        for box, text, score in result:
            if not text:
                continue
            points = tuple((float(point[0]), float(point[1])) for point in box)
            if len(points) != 4:
                continue
            lines.append(OCRLine(text=str(text).strip(), score=float(score), points=points))  # type: ignore[arg-type]
        return lines
