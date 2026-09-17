from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer

FloatArray = NDArray[np.float32]


class SentenceTransformerEmbeddingModel:
    def __init__(
        self,
        model_name: str,
    ) -> None:
        self._model = SentenceTransformer(
            model_name
        )

    def encode(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        embeddings = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )