"""
STEP 4 - LaTeX to PDF (same approach as original project)
=========================================================
Compile .tex files to PDF using lualatex/xelatex with a small Python wrapper.

Why this script:
- CVs in this workflow should compile with lualatex.
- Cover letters in this workflow should compile with xelatex.
- The script gives consistent commands and clear errors.

Examples:
  # Compile a CV (lualatex)
  python step4_pdf.py cv ./cv/main_example.tex

  # Compile a cover letter (xelatex)
  python step4_pdf.py cover ./cover_letters/cover_example.tex

  # Auto mode based on filename/path heuristics
  python step4_pdf.py auto ./cover_letters/cover_company_role.tex

  # Force a specific engine
  python step4_pdf.py compile ./some.tex --engine lualatex
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def fail(message: str) -> int:
    print(f"ERROR: {message}")
    return 1


def ensure_engine_exists(engine: str) -> bool:
    return shutil.which(engine) is not None


def ensure_pandoc_exists() -> bool:
    return shutil.which("pandoc") is not None


def resolve_tex_path(tex_file: Path) -> Path:
    """Resolve tex path; if bare filename is used, also check .\\jobs."""
    if tex_file.exists():
        return tex_file

    if tex_file.parent == Path("."):
        jobs_candidate = Path("jobs") / tex_file.name
        if jobs_candidate.exists():
            return jobs_candidate

    return tex_file


def is_full_latex_document(tex_file: Path) -> bool:
    content = tex_file.read_text(encoding="utf-8", errors="ignore")
    return "\\documentclass" in content and "\\begin{document}" in content


def create_wrapper_document(tex_file: Path) -> Path:
    wrapper = tex_file.with_name(f"__wrapped_{tex_file.stem}.tex")
    wrapper_content = (
        "\\documentclass[11pt,a4paper]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{enumitem}\n"
        "\\setlength{\\parindent}{0pt}\n"
        "\\setlength{\\parskip}{0.4em}\n"
        "\\begin{document}\n"
        f"\\input{{{tex_file.name}}}\n"
        "\\end{document}\n"
    )
    wrapper.write_text(wrapper_content, encoding="utf-8")
    return wrapper


def cleanup_wrapper_artifacts(wrapper_file: Path) -> None:
    for suffix in [".tex", ".aux", ".log", ".out", ".toc", ".pdf", ".docx"]:
        p = wrapper_file.with_suffix(suffix)
        if p.exists():
            p.unlink()


def cleanup_latex_intermediate_files(tex_file: Path) -> None:
    """Remove common LaTeX build artifacts while keeping source .tex and final .pdf."""
    intermediate_suffixes = [
        ".aux",
        ".log",
        ".out",
        ".toc",
        ".fls",
        ".fdb_latexmk",
        ".synctex.gz",
        ".nav",
        ".snm",
        ".vrb",
        ".xdv",
    ]
    for suffix in intermediate_suffixes:
        p = tex_file.with_suffix(suffix)
        if p.exists():
            p.unlink()


def sanitize_filename_field(value: str) -> str:
    """Sanitize one filename field while preserving words and spaces."""
    part = value.strip()
    part = re.sub(r"[<>:\"/\\|?*]+", " ", part)
    part = re.sub(r"\s+", " ", part).strip(" .")
    if not part:
        raise ValueError("Filename fields must contain at least one valid character")
    return part


def build_output_filename_from_parts(
    first_name: str | None,
    surname: str | None,
    position: str | None,
) -> str | None:
    values = [first_name, surname, position]
    provided = [v for v in values if v]
    if not provided:
        return None
    if len(provided) != 3:
        raise ValueError("Provide --first-name, --surname, and --position together")

    safe_first = sanitize_filename_field(first_name or "")
    safe_surname = sanitize_filename_field(surname or "")
    safe_position = sanitize_filename_field(position or "")
    return f"{safe_first} {safe_surname}_{safe_position}.pdf"


def infer_combined_input_file_from_tex(tex_file: Path) -> Path | None:
    """Infer combined Step 2 JSON path from a tex name like 4428861340_cv.tex."""
    stem = tex_file.stem
    match = re.match(r"^(\d+)(?:_(?:cv|cover|cover_letter|cover-letter))?$", stem, flags=re.IGNORECASE)
    if not match:
        return None
    job_id = match.group(1)
    candidate = tex_file.with_name(f"{job_id}.json")
    return candidate if candidate.exists() else None


def read_json_file(json_file: Path) -> dict:
    if not json_file.exists():
        raise ValueError(f"JSON file not found: {json_file}")
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {json_file}") from exc
    if not isinstance(data, dict):
        raise TypeError(f"Expected a JSON object in: {json_file}")
    return data


def extract_name_from_profile(profile: dict) -> tuple[str, str]:
    full_name = str(profile.get("name", "")).strip()
    if not full_name:
        raise ValueError("Profile does not contain a usable 'name' field")
    parts = [p for p in full_name.split() if p]
    if len(parts) < 2:
        raise ValueError("Profile name must include at least first name and surname")
    return parts[0], parts[-1]


def extract_position_from_job(job: dict) -> str:
    position = str(job.get("title") or "").strip()
    if position:
        return position
    position = str(job.get("job_function") or "").strip()
    if position:
        return position
    raise ValueError("Job details do not contain a usable position/title field")


def build_output_filename_from_combined_file(combined_file: Path) -> str:
    combined = read_json_file(combined_file)
    profile = combined.get("profile")
    job = combined.get("job")
    if not isinstance(profile, dict) or not isinstance(job, dict):
        raise TypeError("Combined JSON must contain object fields: profile and job")

    first_name, surname = extract_name_from_profile(profile)
    position = extract_position_from_job(job)
    return build_output_filename_from_parts(first_name, surname, position)


def resolve_output_filename(tex_file: Path) -> str | None:
    inferred_combined = infer_combined_input_file_from_tex(tex_file)
    if inferred_combined:
        return build_output_filename_from_combined_file(inferred_combined)

    return None


def run_latex(engine: str, tex_file: Path, runs: int = 1, output_pdf_name: str | None = None) -> int:
    tex_file = resolve_tex_path(tex_file)

    if not tex_file.exists():
        return fail(f"File not found: {tex_file}")

    if tex_file.suffix.lower() != ".tex":
        return fail(f"Expected a .tex file, got: {tex_file}")

    if not ensure_engine_exists(engine):
        return fail(f"'{engine}' is not installed or not in PATH. Install TeX Live/MacTeX/MiKTeX and retry.")

    workdir = tex_file.parent
    compile_file = tex_file
    wrapped = False
    if not is_full_latex_document(tex_file):
        print("Detected LaTeX fragment (no document preamble). Auto-wrapping for compilation.")
        compile_file = create_wrapper_document(tex_file)
        wrapped = True

    filename = compile_file.name

    # non-stop mode keeps builds non-interactive and easier to script.
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", filename]

    print(f"Compiling with {engine}: {tex_file}")
    try:
        for i in range(1, runs + 1):
            print(f"  Run {i}/{runs}: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                # Print tail of logs to keep output concise but useful.
                stdout_tail = "\n".join(proc.stdout.splitlines()[-30:])
                stderr_tail = "\n".join(proc.stderr.splitlines()[-30:])
                print("\nLaTeX compilation failed.")
                if stdout_tail:
                    print("\n--- stdout (tail) ---")
                    print(stdout_tail)
                if stderr_tail:
                    print("\n--- stderr (tail) ---")
                    print(stderr_tail)
                return 1

        produced_pdf = compile_file.with_suffix(".pdf")
        target_pdf = tex_file.with_name(output_pdf_name) if output_pdf_name else tex_file.with_suffix(".pdf")
        if not produced_pdf.exists():
            return fail(f"Compilation ended but PDF not found: {produced_pdf}")

        if wrapped:
            shutil.copyfile(produced_pdf, target_pdf)
        elif produced_pdf != target_pdf:
            if target_pdf.exists():
                target_pdf.unlink()
            shutil.move(str(produced_pdf), str(target_pdf))

        cleanup_latex_intermediate_files(compile_file)

        print(f"✓ PDF generated: {target_pdf}")
        return 0
    finally:
        if wrapped:
            cleanup_wrapper_artifacts(compile_file)


def run_docx(tex_file: Path, output_docx_name: str | None = None) -> int:
    tex_file = resolve_tex_path(tex_file)

    if not tex_file.exists():
        return fail(f"File not found: {tex_file}")

    if tex_file.suffix.lower() != ".tex":
        return fail(f"Expected a .tex file, got: {tex_file}")

    if not ensure_pandoc_exists():
        return fail("'pandoc' is not installed or not in PATH. Install pandoc and retry.")

    workdir = tex_file.parent
    convert_file = tex_file
    wrapped = False
    if not is_full_latex_document(tex_file):
        print("Detected LaTeX fragment (no document preamble). Auto-wrapping for DOCX conversion.")
        convert_file = create_wrapper_document(tex_file)
        wrapped = True

    target_docx = tex_file.with_name(output_docx_name) if output_docx_name else tex_file.with_suffix(".docx")
    produced_docx = convert_file.with_suffix(".docx")
    cmd = ["pandoc", convert_file.name, "-o", produced_docx.name]

    print(f"Converting to DOCX: {tex_file}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            stdout_tail = "\n".join(proc.stdout.splitlines()[-30:])
            stderr_tail = "\n".join(proc.stderr.splitlines()[-30:])
            print("\nDOCX conversion failed.")
            if stdout_tail:
                print("\n--- stdout (tail) ---")
                print(stdout_tail)
            if stderr_tail:
                print("\n--- stderr (tail) ---")
                print(stderr_tail)
            return 1

        if not produced_docx.exists():
            return fail(f"Conversion ended but DOCX not found: {produced_docx}")

        if wrapped:
            shutil.copyfile(produced_docx, target_docx)
        elif produced_docx != target_docx:
            if target_docx.exists():
                target_docx.unlink()
            shutil.move(str(produced_docx), str(target_docx))

        print(f"✓ DOCX generated: {target_docx}")
        return 0
    finally:
        if wrapped:
            cleanup_wrapper_artifacts(convert_file)


def infer_engine(tex_file: Path) -> str:
    p = str(tex_file).lower()
    if "cover" in p or "cover_letter" in p or "cover-letter" in p:
        return "xelatex"
    return "lualatex"


def command_cv(args: argparse.Namespace) -> int:
    tex_file = resolve_tex_path(Path(args.tex_file))
    try:
        output_name = resolve_output_filename(tex_file)
    except ValueError as exc:
        return fail(str(exc))

    if args.output_format == "pdf":
        return run_latex("lualatex", tex_file, runs=args.runs, output_pdf_name=output_name)

    output_docx_name = output_name[:-4] + ".docx" if output_name else None
    if args.output_format == "docx":
        return run_docx(tex_file, output_docx_name=output_docx_name)

    rc_pdf = run_latex("lualatex", tex_file, runs=args.runs, output_pdf_name=output_name)
    if rc_pdf != 0:
        return rc_pdf
    return run_docx(tex_file, output_docx_name=output_docx_name)


def command_cover(args: argparse.Namespace) -> int:
    tex_file = resolve_tex_path(Path(args.tex_file))
    try:
        output_name = resolve_output_filename(tex_file)
    except ValueError as exc:
        return fail(str(exc))

    if args.output_format == "pdf":
        return run_latex("xelatex", tex_file, runs=args.runs, output_pdf_name=output_name)

    output_docx_name = output_name[:-4] + ".docx" if output_name else None
    if args.output_format == "docx":
        return run_docx(tex_file, output_docx_name=output_docx_name)

    rc_pdf = run_latex("xelatex", tex_file, runs=args.runs, output_pdf_name=output_name)
    if rc_pdf != 0:
        return rc_pdf
    return run_docx(tex_file, output_docx_name=output_docx_name)


def command_auto(args: argparse.Namespace) -> int:
    tex_file = resolve_tex_path(Path(args.tex_file))
    engine = infer_engine(tex_file)
    print(f"Auto-selected engine: {engine}")
    try:
        output_name = resolve_output_filename(tex_file)
    except ValueError as exc:
        return fail(str(exc))

    if args.output_format == "pdf":
        return run_latex(engine, tex_file, runs=args.runs, output_pdf_name=output_name)

    output_docx_name = output_name[:-4] + ".docx" if output_name else None
    if args.output_format == "docx":
        return run_docx(tex_file, output_docx_name=output_docx_name)

    rc_pdf = run_latex(engine, tex_file, runs=args.runs, output_pdf_name=output_name)
    if rc_pdf != 0:
        return rc_pdf
    return run_docx(tex_file, output_docx_name=output_docx_name)


def command_compile(args: argparse.Namespace) -> int:
    tex_file = resolve_tex_path(Path(args.tex_file))
    try:
        output_name = resolve_output_filename(tex_file)
    except ValueError as exc:
        return fail(str(exc))

    if args.output_format == "pdf":
        return run_latex(args.engine, tex_file, runs=args.runs, output_pdf_name=output_name)

    output_docx_name = output_name[:-4] + ".docx" if output_name else None
    if args.output_format == "docx":
        return run_docx(tex_file, output_docx_name=output_docx_name)

    rc_pdf = run_latex(args.engine, tex_file, runs=args.runs, output_pdf_name=output_name)
    if rc_pdf != 0:
        return rc_pdf
    return run_docx(tex_file, output_docx_name=output_docx_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step 4: Compile LaTeX to PDF")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_options(cmd_parser: argparse.ArgumentParser) -> None:
        cmd_parser.add_argument(
            "-f",
            "--output-format",
            choices=["pdf", "docx", "both"],
            default="pdf",
            help="Output format: pdf (default), docx, or both",
        )
        cmd_parser.add_argument("-r", "--runs", type=int, default=1, help="How many latex runs")

    cv = sub.add_parser("cv", help="Compile CV with lualatex")
    cv.add_argument("tex_file", help="Path to .tex file")
    add_common_options(cv)
    cv.set_defaults(func=command_cv)

    cover = sub.add_parser("cover", help="Compile cover letter with xelatex")
    cover.add_argument("tex_file", help="Path to .tex file")
    add_common_options(cover)
    cover.set_defaults(func=command_cover)

    auto = sub.add_parser("auto", help="Infer engine from file/path")
    auto.add_argument("tex_file", help="Path to .tex file")
    add_common_options(auto)
    auto.set_defaults(func=command_auto)

    comp = sub.add_parser("compile", help="Compile with an explicit engine")
    comp.add_argument("tex_file", help="Path to .tex file")
    comp.add_argument("-e", "--engine", choices=["lualatex", "xelatex"], required=True)
    add_common_options(comp)
    comp.set_defaults(func=command_compile)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
