"""
STEP 2 - LinkedIn Job Search (Python)
=====================================
Searches LinkedIn public jobs-guest endpoints and fetches detail for a job.
No API key required.

Run examples:
  /home/denin1/python-version/.venv/bin/python step2_search.py search -l "Copenhagen, Denmark" -q "python developer" --jobage 7 --format table
  /home/denin1/python-version/.venv/bin/python step2_search.py detail 4426311357 --format plain
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"
DEFAULT_PROFILE_FILE = Path(__file__).parent / "profile.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class JobCard:
    id: str
    title: str
    company: str | None
    company_url: str | None
    location: str | None
    date: str | None
    url: str


@dataclass
class JobDetail(JobCard):
    description: str | None
    seniority: str | None
    employment_type: str | None
    job_function: str | None
    industries: str | None
    apply_url: str | None


def write_error(message: str, code: str) -> None:
    sys.stderr.write(json.dumps({"error": message, "code": code}) + "\n")


def html_fetch(url: str, max_retries: int = 6, timeout: int = 15) -> str:
    """Fetch HTML with exponential backoff on 429/5xx. Returns empty string on 404."""
    delay = 0.5
    for attempt in range(max_retries + 1):
        req = Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code == 404:
                return ""
            if exc.code == 429 or 500 <= exc.code <= 599:
                if attempt == max_retries:
                    raise RuntimeError(f"Request failed: HTTP {exc.code}") from exc
                time.sleep(delay + random.uniform(0, 0.5))
                delay = min(delay * 2, 8.0)
                continue
            raise RuntimeError(f"Request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt == max_retries:
                raise RuntimeError(f"Request failed: {exc.reason}") from exc
            time.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 2, 8.0)

    raise RuntimeError("Request failed after max retries")


def strip_tags(text: str | None) -> str | None:
    if text is None:
        return None
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean if clean else None


def first_match(pattern: str, text: str, flags: int = re.IGNORECASE | re.DOTALL) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def parse_job_cards(cards_html: str) -> list[JobCard]:
    cards: list[JobCard] = []
    item_pattern = re.compile(r"(<li[^>]*>.*?</li>)", re.IGNORECASE | re.DOTALL)

    for item_html in item_pattern.findall(cards_html):
        href = first_match(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', item_html)
        if not href:
            continue

        # Extract ID from the card urn first, then fallback to URL patterns.
        id_match = re.search(r'data-entity-urn="urn:li:jobPosting:(\d+)"', item_html)
        if not id_match:
            id_match = re.search(r"/jobs/view/[^/?#]*-(\d+)", href)
        if not id_match:
            id_match = re.search(r"currentJobId=(\d+)", href)
        if not id_match:
            continue

        title = strip_tags(first_match(r"<h3[^>]*>(.*?)</h3>", item_html)) or ""
        company = strip_tags(first_match(r"<h4[^>]*>(.*?)</h4>", item_html))
        company_url = first_match(r"<h4[^>]*>.*?<a[^>]*href=\"([^\"]+)\"", item_html)
        location = strip_tags(first_match(r"class=\"[^\"]*job-search-card__location[^\"]*\"[^>]*>(.*?)<", item_html))
        date = first_match(r"<time[^>]*datetime=\"([^\"]+)\"", item_html)

        cards.append(
            JobCard(
                id=id_match.group(1),
                title=title,
                company=company,
                company_url=company_url,
                location=location,
                date=date,
                url=href,
            )
        )

    # Deduplicate by ID while keeping first occurrence order.
    seen: set[str] = set()
    unique_cards: list[JobCard] = []
    for card in cards:
        if card.id in seen:
            continue
        seen.add(card.id)
        unique_cards.append(card)
    return unique_cards


def parse_detail(detail_html: str, base: JobCard) -> JobDetail:
    description_html = first_match(
        r"<div[^>]*class=\"[^\"]*show-more-less-html__markup[^\"]*\"[^>]*>(.*?)</div>", detail_html
    )
    criteria_block = first_match(
        r"<ul[^>]*class=\"[^\"]*description__job-criteria-list[^\"]*\"[^>]*>(.*?)</ul>", detail_html
    )

    seniority = employment_type = job_function = industries = None
    if criteria_block:
        items = re.findall(r"<li[^>]*>(.*?)</li>", criteria_block, re.IGNORECASE | re.DOTALL)
        for item in items:
            label = strip_tags(first_match(r"<h3[^>]*>(.*?)</h3>", item))
            value = strip_tags(first_match(r"<span[^>]*>(.*?)</span>", item))
            if not label or not value:
                continue
            label_lower = label.lower()
            if "seniority" in label_lower:
                seniority = value
            elif "employment" in label_lower:
                employment_type = value
            elif "job function" in label_lower:
                job_function = value
            elif "industr" in label_lower:
                industries = value

    apply_url = first_match(r"<a[^>]*class=\"[^\"]*topcard__link[^\"]*\"[^>]*href=\"([^\"]+)\"", detail_html)

    return JobDetail(
        id=base.id,
        title=base.title,
        company=base.company,
        company_url=base.company_url,
        location=base.location,
        date=base.date,
        url=base.url,
        description=strip_tags(description_html),
        seniority=seniority,
        employment_type=employment_type,
        job_function=job_function,
        industries=industries,
        apply_url=apply_url,
    )


def build_search_url(args: argparse.Namespace) -> str:
    start = max(args.page - 1, 0) * 10
    params: dict[str, Any] = {
        "keywords": args.query,
        "location": args.location,
        "start": start,
    }

    if args.jobage:
        params["f_TPR"] = f"r{int(args.jobage) * 86400}"

    remote_map = {
        "onsite": "1",
        "remote": "2",
        "hybrid": "3",
    }
    if args.remote:
        params["f_WT"] = remote_map[args.remote]

    return f"{SEARCH_URL}?{urlencode(params)}"


def render_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "No results."

    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    def line(values: list[str]) -> str:
        return " | ".join(v.ljust(widths[c]) for v, c in zip(values, columns))

    header = line(columns)
    sep = "-+-".join("-" * widths[c] for c in columns)
    body = [line([str(r.get(c, "")) for c in columns]) for r in rows]
    return "\n".join([header, sep, *body])


def print_search(cards: list[JobCard], fmt: str) -> None:
    data = [asdict(c) for c in cards]

    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if fmt == "table":
        rows = [
            {
                "id": c.id,
                "title": c.title,
                "company": c.company or "",
                "location": c.location or "",
                "date": c.date or "",
            }
            for c in cards
        ]
        print(render_table(rows, ["id", "title", "company", "location", "date"]))
        return

    # plain
    for c in cards:
        print(f"[{c.id}] {c.title}")
        print(f"  Company : {c.company or '-'}")
        print(f"  Location: {c.location or '-'}")
        print(f"  Date    : {c.date or '-'}")
        print(f"  URL     : {c.url}")
        print()


def print_detail(detail: JobDetail, fmt: str) -> None:
    data = asdict(detail)
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"[{detail.id}] {detail.title}")
    print(f"Company         : {detail.company or '-'}")
    print(f"Location        : {detail.location or '-'}")
    print(f"Date            : {detail.date or '-'}")
    print(f"Seniority       : {detail.seniority or '-'}")
    print(f"Employment Type : {detail.employment_type or '-'}")
    print(f"Job Function    : {detail.job_function or '-'}")
    print(f"Industries      : {detail.industries or '-'}")
    print(f"Apply URL       : {detail.apply_url or '-'}")
    print(f"Job URL         : {detail.url}")
    print()
    print("Description:")
    print(detail.description or "-")


def load_profile(profile_file: Path) -> dict[str, Any]:
    if not profile_file.exists():
        raise ValueError(
            f"Profile file not found: {profile_file}. Run 'python step1_profile.py' first, "
            "or pass --profile-file <path>."
        )
    try:
        return json.loads(profile_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in profile file: {profile_file}") from exc


def write_combined_output(profile: dict[str, Any], detail: JobDetail, output_file: Path) -> None:
    combined: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "step2_search.py",
        "profile": profile,
        "job": asdict(detail),
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")


def search_command(args: argparse.Namespace) -> int:
    url = build_search_url(args)
    cards_html = html_fetch(url)
    cards = parse_job_cards(cards_html)

    if args.limit is not None:
        cards = cards[: max(args.limit, 0)]

    print_search(cards, args.format)
    return 0


def detail_command(args: argparse.Namespace) -> int:
    target = args.target

    # Accept ID, URL, or URN.
    id_match = re.search(r"(\d{6,})", target)
    if not id_match:
        raise ValueError("Could not extract a job ID from input")
    job_id = id_match.group(1)

    detail_html = html_fetch(f"{DETAIL_URL}/{job_id}")
    if not detail_html:
        raise ValueError(f"Job not found for ID {job_id}")

    # Pull base fields from detail page.
    title = (
        strip_tags(first_match(r"<h1[^>]*class=\"[^\"]*top-card-layout__title[^\"]*\"[^>]*>(.*?)</h1>", detail_html))
        or ""
    )
    company = strip_tags(
        first_match(r"<a[^>]*class=\"[^\"]*topcard__org-name-link[^\"]*\"[^>]*>(.*?)</a>", detail_html)
    )
    company_url = first_match(r"<a[^>]*class=\"[^\"]*topcard__org-name-link[^\"]*\"[^>]*href=\"([^\"]+)\"", detail_html)
    location = strip_tags(
        first_match(r"<span[^>]*class=\"[^\"]*topcard__flavor--bullet[^\"]*\"[^>]*>(.*?)</span>", detail_html)
    )
    date = first_match(r"datetime=\"([^\"]+)\"", detail_html)
    job_url = f"https://www.linkedin.com/jobs/view/{job_id}"

    base = JobCard(
        id=job_id,
        title=title,
        company=company,
        company_url=company_url,
        location=location,
        date=date,
        url=job_url,
    )

    detail = parse_detail(detail_html, base)

    if args.combine_output:
        profile = load_profile(Path(args.profile_file))
        output_file = Path(args.combine_output)
        write_combined_output(profile, detail, output_file)
        print(f"Combined profile+job JSON written to: {output_file}")

    print_detail(detail, args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Step 2: Search LinkedIn public jobs in Python",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search job listings")
    search.add_argument("-l", "--location", required=True, help="Location text, e.g. 'Berlin, Germany'")
    search.add_argument("-q", "--query", default="", help="Keyword query")
    search.add_argument("--jobage", type=int, choices=[1, 7, 14, 30], help="Posted within N days")
    search.add_argument("--remote", choices=["remote", "hybrid", "onsite"], help="Workplace type filter")
    search.add_argument("--page", type=int, default=1, help="Page number (1-indexed)")
    search.add_argument("-n", "--limit", type=int, help="Maximum number of results")
    search.add_argument("--format", choices=["json", "table", "plain"], default="json")
    search.set_defaults(func=search_command)

    detail = subparsers.add_parser("detail", help="Fetch full job detail")
    detail.add_argument("target", help="Job ID, LinkedIn URL, or URN")
    detail.add_argument("--format", choices=["json", "plain"], default="json")
    detail.add_argument(
        "--combine-output",
        help="Optional path to write combined profile + job detail JSON",
    )
    detail.add_argument(
        "--profile-file",
        default=str(DEFAULT_PROFILE_FILE),
        help="Path to profile JSON used with --combine-output",
    )
    detail.set_defaults(func=detail_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI should present friendly error.
        write_error(str(exc), "SEARCH_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
