from __future__ import annotations

import re
from typing import Any

LABEL_PATTERN = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:\\.|[^"])*)"')


def parse_prometheus_text(text: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            metric, value_text = line.rsplit(" ", 1)
            value = float(value_text)
        except ValueError:
            continue

        name, labels = _parse_metric(metric)
        samples.append({"name": name, "labels": labels, "value": value})

    return samples


def sum_metric(
    samples: list[dict[str, Any]],
    name: str,
    labels: dict[str, str] | None = None,
) -> float:
    expected = labels or {}
    total = 0.0
    for sample in samples:
        if sample["name"] != name:
            continue
        sample_labels = sample["labels"]
        if all(sample_labels.get(key) == value for key, value in expected.items()):
            total += float(sample["value"])
    return total


def _parse_metric(metric: str) -> tuple[str, dict[str, str]]:
    if "{" not in metric:
        return metric, {}

    name, raw_labels = metric.split("{", 1)
    raw_labels = raw_labels.removesuffix("}")
    labels = {
        match.group(1): _unescape_label(match.group(2))
        for match in LABEL_PATTERN.finditer(raw_labels)
    }
    return name, labels


def _unescape_label(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\n", "\n").replace(r"\\", "\\")
