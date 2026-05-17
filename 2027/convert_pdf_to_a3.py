#!/usr/bin/env python3
"""Convert a PDF to A3 page size.

This script uses Ghostscript (gs) to rewrite a PDF so that each page is
scaled to fit an A3 sheet.

Example:
  python convert_pdf_to_a3.py tidal_calendar_2027.pdf tidal_calendar_2027_A3.pdf

If Ghostscript isn't installed, install it on macOS with:
  brew install ghostscript
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _find_ghostscript() -> str | None:
    # Common executable names across platforms.
    for candidate in ("gs", "gsc", "gswin64c", "gswin32c"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def convert_to_a3(
    input_pdf: Path,
    output_pdf: Path,
    *,
    paper: str = "a3",
    autorotate: str = "PageByPage",
) -> None:
    gs = _find_ghostscript()
    if not gs:
        raise RuntimeError(
            "Ghostscript executable not found (expected `gs`).\n"
            "Install it (macOS): `brew install ghostscript`\n"
            "Or ensure `gs` is on your PATH."
        )

    # Ghostscript options:
    # -dPDFFitPage: scales page contents to fit the requested paper size
    # -dFIXEDMEDIA: forces output MediaBox to the paper size
    # -dAutoRotatePages: controls auto-rotation behavior
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
        f"-dAutoRotatePages=/{autorotate}",
        f"-sPAPERSIZE={paper}",
        "-dFIXEDMEDIA",
        "-dPDFFitPage",
        "-o",
        str(output_pdf),
        str(input_pdf),
    ]

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to A3 page size (scales content to fit)."
    )
    parser.add_argument(
        "input_pdf",
        nargs="?",
        default="tidal_calendar_2027.pdf",
        help="Input PDF path (default: tidal_calendar_2027.pdf)",
    )
    parser.add_argument(
        "output_pdf",
        nargs="?",
        default="tidal_calendar_2027_A3.pdf",
        help="Output PDF path (default: tidal_calendar_2027_A3.pdf)",
    )
    parser.add_argument(
        "--paper",
        default="a3",
        help="Ghostscript paper name (default: a3)",
    )
    parser.add_argument(
        "--autorotate",
        choices=["None", "All", "PageByPage"],
        default="PageByPage",
        help="Ghostscript auto-rotate mode (default: PageByPage)",
    )

    args = parser.parse_args()

    input_pdf = Path(args.input_pdf)
    output_pdf = Path(args.output_pdf)

    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    convert_to_a3(input_pdf, output_pdf, paper=args.paper, autorotate=args.autorotate)
    print(f"Wrote: {output_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
