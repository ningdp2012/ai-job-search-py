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
import shutil
import subprocess
from pathlib import Path


def fail(message: str) -> int:
    print(f"ERROR: {message}")
    return 1


def ensure_engine_exists(engine: str) -> bool:
    return shutil.which(engine) is not None


def is_full_latex_document(tex_file: Path) -> bool:
    content = tex_file.read_text(encoding="utf-8", errors="ignore")
    return "\\documentclass" in content and "\\begin{document}" in content


def create_wrapper_document(tex_file: Path) -> Path:
    wrapper = tex_file.with_name(f"__wrapped_{tex_file.stem}.tex")
    wrapper_content = (
        "\\documentclass[11pt,a4paper]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{enumitem}\n"
        "\\usepackage[hidelinks]{hyperref}\n"
        "\\setlength{\\parindent}{0pt}\n"
        "\\setlength{\\parskip}{0.4em}\n"
        "\\begin{document}\n"
        f"\\input{{{tex_file.name}}}\n"
        "\\end{document}\n"
    )
    wrapper.write_text(wrapper_content, encoding="utf-8")
    return wrapper


def cleanup_wrapper_artifacts(wrapper_file: Path) -> None:
    for suffix in [".tex", ".aux", ".log", ".out", ".toc", ".pdf"]:
        p = wrapper_file.with_suffix(suffix)
        if p.exists():
            p.unlink()


def run_latex(engine: str, tex_file: Path, runs: int = 1) -> int:
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
        target_pdf = tex_file.with_suffix(".pdf")
        if not produced_pdf.exists():
            return fail(f"Compilation ended but PDF not found: {produced_pdf}")

        if wrapped:
            shutil.copyfile(produced_pdf, target_pdf)

        print(f"✓ PDF generated: {target_pdf}")
        return 0
    finally:
        if wrapped:
            cleanup_wrapper_artifacts(compile_file)


def infer_engine(tex_file: Path) -> str:
    p = str(tex_file).lower()
    if "cover" in p or "cover_letter" in p or "cover-letter" in p:
        return "xelatex"
    return "lualatex"


def command_cv(args: argparse.Namespace) -> int:
    return run_latex("lualatex", Path(args.tex_file), runs=args.runs)


def command_cover(args: argparse.Namespace) -> int:
    return run_latex("xelatex", Path(args.tex_file), runs=args.runs)


def command_auto(args: argparse.Namespace) -> int:
    tex_file = Path(args.tex_file)
    engine = infer_engine(tex_file)
    print(f"Auto-selected engine: {engine}")
    return run_latex(engine, tex_file, runs=args.runs)


def command_compile(args: argparse.Namespace) -> int:
    return run_latex(args.engine, Path(args.tex_file), runs=args.runs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step 4: Compile LaTeX to PDF")
    sub = parser.add_subparsers(dest="command", required=True)

    cv = sub.add_parser("cv", help="Compile CV with lualatex")
    cv.add_argument("tex_file", help="Path to .tex file")
    cv.add_argument("--runs", type=int, default=1, help="How many latex runs")
    cv.set_defaults(func=command_cv)

    cover = sub.add_parser("cover", help="Compile cover letter with xelatex")
    cover.add_argument("tex_file", help="Path to .tex file")
    cover.add_argument("--runs", type=int, default=1, help="How many latex runs")
    cover.set_defaults(func=command_cover)

    auto = sub.add_parser("auto", help="Infer engine from file/path")
    auto.add_argument("tex_file", help="Path to .tex file")
    auto.add_argument("--runs", type=int, default=1, help="How many latex runs")
    auto.set_defaults(func=command_auto)

    comp = sub.add_parser("compile", help="Compile with an explicit engine")
    comp.add_argument("tex_file", help="Path to .tex file")
    comp.add_argument("--engine", choices=["lualatex", "xelatex"], required=True)
    comp.add_argument("--runs", type=int, default=1, help="How many latex runs")
    comp.set_defaults(func=command_compile)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
