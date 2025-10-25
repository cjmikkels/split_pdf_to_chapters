"""Command line interface for splitting a PDF into chapter files.

This module exposes :func:`split_pdf_by_outlines` which performs the heavy
lifting, and a ``main`` entrypoint used by the ``split-pdf-to-chapters``
console script that is declared in :mod:`pyproject.toml`.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

from PyPDF2 import PdfReader, PdfWriter


@dataclass
class OutlineEntry:
    """A flattened representation of a bookmark entry."""

    titles: List[str]
    page_index: int

    @property
    def display_name(self) -> str:
        """Join the collected titles with ``" - "``."""

        return " - ".join(self.titles)


def _clean_title(raw: str) -> str:
    """Return a filesystem-safe representation of ``raw``."""

    cleaned = unicodedata.normalize("NFKD", raw).strip()
    cleaned = re.sub(r"[\s\u00a0]+", " ", cleaned)  # collapse whitespace
    cleaned = cleaned.replace("/", "-")
    cleaned = re.sub(r"[\000-\037\177]+", "", cleaned)  # control chars
    cleaned = cleaned[:150]  # guard against very long names
    return cleaned or "untitled"


def _sanitize_filename(name: str) -> str:
    """Return a slugified filename (without extension)."""

    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "", name).strip().lower()
    name = re.sub(r"[\s-]+", "-", name)
    return name or "untitled"


def _extract_title(item: object) -> str:
    title = getattr(item, "title", None)
    if title:
        return _clean_title(str(title))
    if hasattr(item, "get"):
        try:
            raw = item.get("/Title")
            if raw:
                return _clean_title(str(raw))
        except Exception:  # pragma: no cover - defensive
            pass
    return _clean_title(str(item))


def _destination_for_item(item: object) -> object:
    destination = getattr(item, "destination", None)
    if destination is not None:
        return destination
    destination = getattr(item, "dest", None)
    if destination is not None:
        return destination
    return item


def _child_items(item: object) -> Sequence[object] | None:
    children = getattr(item, "children", None)
    if children:
        return list(children)
    return None


def _iter_outline(
    reader: PdfReader, outline: Iterable[object], parents: List[str] | None = None
) -> Iterator[OutlineEntry]:
    parents = list(parents or [])
    for entry in outline:
        if isinstance(entry, list):
            yield from _iter_outline(reader, entry, parents)
            continue

        title = _extract_title(entry)
        destination = _destination_for_item(entry)
        try:
            page_index = reader.get_destination_page_number(destination)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unable to resolve page number for outline '{title}'") from exc

        new_parents = parents + [title]
        children = _child_items(entry)
        if children:
            yield from _iter_outline(reader, children, new_parents)
        else:
            yield OutlineEntry(new_parents, page_index)


def _flatten_outline(reader: PdfReader) -> List[OutlineEntry]:
    outline = getattr(reader, "outline", None) or getattr(reader, "outlines", None)
    if not outline:
        return []
    entries = list(_iter_outline(reader, outline))
    entries.sort(key=lambda item: item.page_index)
    deduped: List[OutlineEntry] = []
    seen_pages = set()
    for entry in entries:
        if entry.page_index in seen_pages:
            continue
        seen_pages.add(entry.page_index)
        deduped.append(entry)
    return deduped


def split_pdf_by_outlines(input_pdf: Path, output_dir: Path) -> List[Path]:
    """Split ``input_pdf`` into per-chapter PDFs using the document outline."""

    reader = PdfReader(str(input_pdf))
    entries = _flatten_outline(reader)
    if not entries:
        raise ValueError("The supplied PDF does not contain any outline/bookmark data.")

    output_dir.mkdir(parents=True, exist_ok=True)

    total_pages = len(reader.pages)
    produced_files: List[Path] = []
    used_names: dict[str, int] = {}

    for index, entry in enumerate(entries):
        start = entry.page_index
        end = entries[index + 1].page_index if index + 1 < len(entries) else total_pages
        if start >= end:  # pragma: no cover - defensive
            continue

        writer = PdfWriter()
        for page_number in range(start, end):
            writer.add_page(reader.pages[page_number])

        base_name = _sanitize_filename(entry.display_name)
        count = used_names.get(base_name, 0)
        used_names[base_name] = count + 1
        if count:
            file_name = f"{base_name}-{count + 1:02d}.pdf"
        else:
            file_name = f"{base_name}.pdf"

        output_path = output_dir / file_name
        with output_path.open("wb") as handle:
            writer.write(handle)
        produced_files.append(output_path)

    return produced_files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Split a PDF into separate files using its deepest outline entries."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file to split")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Directory where the chapter PDFs will be written (defaults to <pdf>-chapters)",
    )

    args = parser.parse_args(argv)
    input_pdf: Path = args.pdf
    output_dir: Path = args.output or input_pdf.with_name(f"{input_pdf.stem}-chapters")

    produced = split_pdf_by_outlines(input_pdf, output_dir)
    print(f"Created {len(produced)} files in {output_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
