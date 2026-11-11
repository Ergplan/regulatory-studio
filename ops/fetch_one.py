"""Kept for old notes: use `regstudio fetch <url> <commission> <doc_type> [--date] [--title] [--case]`.

That command uses the downloader's polite client (robots.txt, a pause per host, and repair of
incomplete certificate chains, which APTEL needs) and writes the same inbox metadata.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from regstudio.cli import main  # noqa: E402

main(["fetch", *sys.argv[1:]])
