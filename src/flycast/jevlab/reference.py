"""TF-IDF plus logistic reference on the same splits."""

from __future__ import annotations

import time

import numpy as np

from flycast.jevlab.readout import fit_temperature, metrics

__all__ = ["tfidf_latency_ms", "tfidf_reference"]

_TEMPERATURES = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)


def _logits(clf, matrix) -> np.ndarray:
    classes = [int(c) for c in clf.classes_]
    width = max(classes) + 1
    if clf.coef_.shape[0] == 1:
        logits = np.zeros((matrix.shape[0], width), dtype=np.float64)
        logits[:, classes[1]] = np.asarray(clf.decision_function(matrix), dtype=np.float64)
        return logits
    raw = np.asarray(clf.decision_function(matrix), dtype=np.float64)
    if raw.ndim == 1:
        raw = raw.reshape(-1, 1)
    logits = np.zeros((matrix.shape[0], width), dtype=np.float64)
    logits[:, classes] = raw
    return logits


def _proba(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / temperature
    scaled -= scaled.max(axis=1, keepdims=True)
    ex = np.exp(scaled)
    return ex / ex.sum(axis=1, keepdims=True)


def tfidf_reference(
    train_texts,
    y_train,
    valid_texts,
    y_valid,
    test_texts,
    y_test,
    *,
    seed: int,
) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    started = time.perf_counter()
    vectorizer = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=2, sublinear_tf=True
    )
    x_train = vectorizer.fit_transform(train_texts)
    x_valid = vectorizer.transform(valid_texts)
    x_test = vectorizer.transform(test_texts)
    y_train = np.asarray(y_train)
    y_valid = np.asarray(y_valid)
    y_test = np.asarray(y_test)
    best = None
    for c_value in (0.3, 1.0, 3.0):
        clf = LogisticRegression(C=c_value, max_iter=2000, random_state=seed)
        clf.fit(x_train, y_train)
        logits = _logits(clf, x_valid)
        temperature = fit_temperature(logits, y_valid, _TEMPERATURES)
        proba = _proba(logits, temperature)
        score = metrics(proba, y_valid)["nll"]
        if best is None or score < best[0]:
            best = (score, c_value, temperature, clf)
    assert best is not None
    _score, c_value, temperature, clf = best
    valid_metrics = metrics(_proba(_logits(clf, x_valid), temperature), y_valid)
    test_metrics = metrics(_proba(_logits(clf, x_test), temperature), y_test)
    return {
        "valid": valid_metrics,
        "test": test_metrics,
        "C": c_value,
        "temperature": temperature,
        "n_features": int(len(vectorizer.vocabulary_)),
        "fit_seconds": time.perf_counter() - started,
        "vectorizer": vectorizer,
        "clf": clf,
    }


def tfidf_latency_ms(vectorizer, clf, texts, n: int = 1000) -> float:
    if not texts:
        raise ValueError("texts is empty")
    samples = []
    for i in range(n):
        text = texts[i % len(texts)]
        started = time.perf_counter()
        matrix = vectorizer.transform([text])
        clf.predict(matrix)
        samples.append((time.perf_counter() - started) * 1000.0)
    return float(np.median(samples))
