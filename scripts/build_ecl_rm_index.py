from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_KEYWORDS = [
    "RUNSPEC",
    "DIMENS",
    "TABDIMS",
    "WELLDIMS",
    "OIL",
    "WATER",
    "GAS",
    "METRIC",
    "START",
    "GRID",
    "DX",
    "DY",
    "DZ",
    "TOPS",
    "PORO",
    "PERMX",
    "PERMY",
    "PERMZ",
    "MULTPV",
    "ACTNUM",
    "PROPS",
    "DENSITY",
    "PVTW",
    "PVTO",
    "PVDO",
    "PVDG",
    "PVTG",
    "ROCK",
    "SWOF",
    "SGOF",
    "REGIONS",
    "PVTNUM",
    "SATNUM",
    "ROCKNUM",
    "FIPNUM",
    "SOLUTION",
    "PRESSURE",
    "SWAT",
    "SGAS",
    "SCHEDULE",
    "RPTRST",
    "RPTSCHED",
    "WELSPECS",
    "COMPDAT",
    "WCONPROD",
    "WCONINJE",
    "DATES",
    "SUMMARY",
    "FOPR",
    "FWPR",
    "FWIR",
    "WOPR",
    "WWPR",
    "WBHP",
    "WWCT",
]


SECTION_NAMES = [
    "RUNSPEC",
    "GRID",
    "EDIT",
    "PROPS",
    "REGIONS",
    "SOLUTION",
    "SUMMARY",
    "SCHEDULE",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local keyword index from an ECLIPSE Reference Manual HTML folder.")
    parser.add_argument("--source", required=True, type=Path, help="Path to ecl_rm HTML directory.")
    parser.add_argument("--output", required=True, type=Path, help="Output directory for generated local index.")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=DEFAULT_KEYWORDS,
        help="Keywords to include in quick_reference.json.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"Manual source directory does not exist: {source}")

    text_dir = output / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    entries: dict[str, dict[str, object]] = {}
    html_files = sorted(source.glob("*.html"))
    for html_path in html_files:
        raw = html_path.read_text(encoding="iso-8859-1", errors="replace")
        title = _extract_title(raw) or html_path.stem.upper()
        keyword = _keyword_from_title(title, html_path)
        plain = _html_to_text(raw)
        description = _extract_description(plain, keyword)
        sections = _extract_applicable_sections(plain)
        text_path = text_dir / f"{keyword}.txt"
        text_path.write_text(plain, encoding="utf-8")
        entries[keyword] = {
            "keyword": keyword,
            "title": title,
            "description": description,
            "sections": sections,
            "source_html": str(html_path),
            "local_text": str(text_path),
            "size_bytes": html_path.stat().st_size,
        }

    quick_keywords = [item.upper() for item in args.keywords]
    quick_reference = {keyword: entries[keyword] for keyword in quick_keywords if keyword in entries}
    missing_quick_keywords = [keyword for keyword in quick_keywords if keyword not in entries]

    manifest = {
        "source": str(source),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "html_file_count": len(html_files),
        "keyword_count": len(entries),
        "quick_keyword_count": len(quick_reference),
        "missing_quick_keywords": missing_quick_keywords,
        "encoding": "source iso-8859-1, generated utf-8",
        "note": "Generated local cache for WorkNotOver deck debugging. Do not commit generated manual text.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "keywords_index.json").write_text(
        json.dumps(dict(sorted(entries.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "quick_reference.json").write_text(
        json.dumps(dict(sorted(quick_reference.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def _extract_title(raw: str) -> str:
    match = re.search(r"<title>(.*?)</title>", raw, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return html.unescape(_strip_tags(match.group(1))).strip()


def _keyword_from_title(title: str, path: Path) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", " ", title).strip().split(" ")[0] if title else ""
    return (token or path.stem).upper()


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|h1|h2|h3|h4|tr|td|th|li|table|div|blockquote)>", "\n", raw)
    text = _strip_tags(raw)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip() + "\n"


def _strip_tags(value: str) -> str:
    return re.sub(r"(?s)<[^>]+>", " ", value)


def _extract_description(text: str, keyword: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.upper() == keyword:
            for candidate in lines[index + 1 :]:
                if candidate.upper() != keyword:
                    return candidate[:500]
    return lines[0][:500] if lines else ""


def _extract_applicable_sections(text: str) -> list[str]:
    lines = [line.strip().upper() for line in text.splitlines() if line.strip()]
    result: list[str] = []
    for index, line in enumerate(lines):
        if line == "X" and index + 1 < len(lines) and lines[index + 1] in SECTION_NAMES:
            result.append(lines[index + 1])
    return sorted(set(result), key=SECTION_NAMES.index)


if __name__ == "__main__":
    main()
