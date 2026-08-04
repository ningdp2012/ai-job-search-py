# ai-job-search-py

Lightweight Python workflow for job-search tasks:

- Create and store a personal profile interactively.
- Search LinkedIn public job listings and inspect job details.
- Manually pass selected job data to an LLM (ChatGPT, Gemini, etc.) to generate tailored CV/cover-letter content (Step 3).
- Compile CV and cover-letter LaTeX files to PDF with the correct engine.

This folder is a minimal script-based companion to the larger workspace in [../ai-job-search](../ai-job-search).

## Project Files

- `step1_profile.py`: Interactive profile setup and save to `profile.json`.
- `step2_search.py`: LinkedIn job search + job detail fetch.
- `step4_pdf.py`: Compile `.tex` to PDF using `lualatex`/`xelatex`.

## Requirements

- Python 3.10+
- Internet connection (for LinkedIn search in Step 2)
- A LaTeX distribution with `lualatex` and `xelatex` in PATH (for Step 4)
  - Windows: MiKTeX or TeX Live

## Quick Start

From this folder:

```powershell
# Optional: activate local virtual environment
.\.venv\Scripts\Activate.ps1

# 1) Create/update profile
python step1_profile.py

# 2) Search jobs
python step2_search.py search -l "Copenhagen, Denmark" -q "infrastructure engineer" --jobage 7 --format table

# 2b) Inspect one job in detail (replace with a real ID/URL)


# 2c) Create a single combined file (profile + job detail) for Step 3
python step2_search.py detail --format json 4426311357 --combine-output .\jobs\4426311357.json

# 3) Manual AI step (outside this repo for now)
#    - Paste Step 2 output into ChatGPT/Gemini/etc.
#    - Ask it to produce CV/cover-letter text in your LaTeX template style
#    - Save/update .tex files in ../ai-job-search/cv or ../ai-job-search/cover_letters

# 4) Compile LaTeX to PDF
python step4_pdf.py cv ..\ai-job-search\cv\main_example.tex
python step4_pdf.py cover ..\ai-job-search\cover_letters\cover_example.tex
```

## Step 1: Profile Setup

Run:

```powershell
python step1_profile.py
```

What it does:

- Prompts for identity, education, experience, skills, and job preferences.
- Saves data to `profile.json` in this folder.
- If a profile already exists, asks before overwriting.

## Step 2: LinkedIn Search

### Search Command

```powershell
python step2_search.py search -l "City, Country" -q "keyword query" [options]
```

Options:

- `--jobage {1,7,14,30}`: posted within N days
- `--remote {remote,hybrid,onsite}`: workplace type
- `--page N`: page number (10 results per page)
- `-n, --limit N`: max returned results
- `--format {json,table,plain}`

Examples:

```powershell
python step2_search.py search -l "Berlin, Germany" -q "data engineer" --jobage 14 --format table
python step2_search.py search -l "Remote" -q "machine learning" --remote remote --limit 5 --format json
```

### Detail Command

```powershell
python step2_search.py detail [--format json|plain] <job-id-or-link>
```

Optional combine output:

```powershell
python step2_search.py detail --format json <job-id-or-link> --combine-output .\job_inputs\job_<id>.json [--profile-file .\profile.json]
```

Accepted input for `detail`:

- LinkedIn job ID
- LinkedIn job URL
- LinkedIn URN containing a job ID

Examples:

```powershell
python step2_search.py detail 4426311357 --format plain
python step2_search.py detail "https://www.linkedin.com/jobs/view/4426311357" --format json
python step2_search.py detail 4426311357 --format json --combine-output .\jobs\4426311357.json
```

Notes:

- Step 2 uses LinkedIn public jobs-guest endpoints.
- Network or rate-limiting errors are retried with backoff.
- With `--combine-output`, Step 2 writes a single JSON containing both your profile and the fetched job details.

## Step 3: Manual AI Drafting (Current)

Current state:

- Step 3 is manual.
- You can take output from Step 2 in two ways:
  - Search/detail output directly from terminal.
  - A single combined JSON file created via `--combine-output`.
- Paste that information into an AI assistant such as ChatGPT or Gemini.
- The AI returns draft content for a CV and/or cover letter, which you place into your `.tex` files.

Typical prompt pattern:

```text
Using my profile and this job posting output, draft a targeted CV  and cover letter .
Keep claims factual and aligned with my real experience.
Return a complete LaTeX document structure.
```

Future direction:

- Step 3 is planned to be automated in this project.
- The target flow is: Step 2 output -> automated prompt/transform -> generated `.tex` content -> Step 4 PDF compilation.
- Until then, keep Step 3 as a human-reviewed manual checkpoint.

## Step 4: LaTeX to PDF

`step4_pdf.py` provides 4 modes:

- `cv`: force `lualatex`
- `cover`: force `xelatex`
- `auto`: infer engine from file/path
- `compile`: explicitly choose engine

Examples:

```powershell
# CV with lualatex
python step4_pdf.py cv ..\ai-job-search\cv\main_example.tex

# Cover letter with xelatex
python step4_pdf.py cover ..\ai-job-search\cover_letters\cover_example.tex

# Auto-select engine by filename/path heuristics
python step4_pdf.py auto ..\ai-job-search\cover_letters\cover_example.tex

# Explicit engine
python step4_pdf.py compile ..\ai-job-search\cv\main_example.tex --engine lualatex --runs 2
```

If compilation fails, the script prints the tail of LaTeX stdout/stderr for faster debugging.

## Troubleshooting

- `'python' is not recognized`:
  - Use `py` instead of `python`, or activate `.venv` first.
- `'lualatex'` or `'xelatex'` not found:
  - Install MiKTeX/TeX Live and ensure binaries are in PATH.
- Step 2 returns no results:
  - Try a broader location/query, remove filters, or retry later.

## Output Files

- `profile.json`: generated by Step 1.
- `*.pdf` next to your `.tex` source files: generated by Step 4.

## Disclaimer

LinkedIn page structure and public endpoint behavior can change at any time. If parsing/search breaks, update the extraction logic in `step2_search.py`.
