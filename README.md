# split-pdf-to-chapters

A small command line utility that splits a PDF into individual chapter files
based on the deepest outline entries (bookmarks) embedded in the document.

## Installation

```bash
pip install .
```

This installs a ``split-pdf-to-chapters`` console script.

## Usage

```bash
split-pdf-to-chapters path/to/book.pdf
```

By default the command will create a sibling directory named
``book-chapters`` that contains a PDF for each deepest outline entry. Supply an
explicit output directory to override the destination:

```bash
split-pdf-to-chapters path/to/book.pdf /desired/output/dir
```

Each generated file is named after the full path of outline titles that lead to
the leaf bookmark (for example ``part-i-chapter-1-introduction.pdf``).

If the PDF does not contain outline metadata the command exits with an error.
