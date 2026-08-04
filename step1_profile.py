"""
STEP 1 - Profile Setup
======================
Collects your personal information interactively and saves it to profile.json.
This replaces the /setup command in the original project.

Run with:
    python step1_profile.py
"""

import json
from pathlib import Path

PROFILE_FILE = Path(__file__).parent / "profile.json"


def ask(prompt: str, default: str = "") -> str:
    """Ask a question and return the answer. Shows default if provided."""
    if default:
        answer = input(f"{prompt} [{default}]: ").strip()
        return answer if answer else default
    return input(f"{prompt}: ").strip()


def ask_list(prompt: str) -> list[str]:
    """Ask for a comma-separated list and return as a Python list."""
    raw = input(f"{prompt} (comma-separated): ").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def collect_profile() -> dict:
    print("\n=== JOB SEARCH PROFILE SETUP ===\n")
    print("Answer the questions below. Press Enter to skip optional fields.\n")

    profile = {}

    # --- Identity ---
    print("--- Identity ---")
    profile["name"] = ask("Full name")
    profile["email"] = ask("Email address")
    profile["phone"] = ask("Phone number (optional)")
    profile["location"] = ask("City, Country (e.g. Copenhagen, Denmark)")
    profile["linkedin"] = ask("LinkedIn URL (optional)")
    profile["languages"] = ask_list("Languages you speak")

    # --- Employment status ---
    print("\n--- Current Status ---")
    profile["employment_status"] = ask("Current status (e.g. employed, open to opportunities, actively looking)")
    profile["linkedin_headline"] = ask("LinkedIn headline (1 sentence)")

    # --- Education ---
    print("\n--- Education (most recent degree) ---")
    profile["education"] = {
        "degree": ask("Degree level (e.g. MSc, BSc, PhD)"),
        "field": ask("Field of study"),
        "institution": ask("Institution name"),
        "year_end": ask("Graduation year"),
        "thesis": ask("Thesis title (optional)"),
    }

    # --- Experience ---
    print("\n--- Professional Experience ---")
    print("Enter your jobs one by one, most recent first. Press Enter with no title to stop.\n")
    experiences = []
    job_num = 1
    while True:
        print(f"  Job #{job_num}:")
        title = ask("  Job title (or press Enter to finish)")
        if not title:
            break
        experiences.append(
            {
                "title": title,
                "company": ask("  Company name"),
                "location": ask("  Location"),
                "start_date": ask("  Start date (e.g. Jan 2022)"),
                "end_date": ask("  End date (or 'present')"),
                "responsibilities": ask_list("  Key responsibilities / achievements"),
            }
        )
        print()
        job_num += 1
    profile["experience"] = experiences

    # --- Skills ---
    print("\n--- Technical Skills ---")
    profile["skills"] = {
        "primary": ask_list("Primary skills (most important)"),
        "secondary": ask_list("Secondary skills"),
        "domain": ask_list("Domain expertise (e.g. machine learning, fintech)"),
        "tools": ask_list("Tools & software"),
    }

    # --- Job search preferences ---
    print("\n--- Job Search Preferences ---")
    profile["target_roles"] = ask_list("Target job titles")
    profile["target_sectors"] = ask_list("Target industries/sectors")
    profile["target_locations"] = ask_list("Preferred locations (or 'Remote')")
    profile["dealbreakers"] = ask_list("Deal-breakers (things you won't accept)")

    return profile


def save_profile(profile: dict) -> None:
    PROFILE_FILE.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n✓ Profile saved to: {PROFILE_FILE}")


def load_profile() -> dict | None:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    return None


def show_profile(profile: dict) -> None:
    print("\n=== YOUR PROFILE ===")
    print(json.dumps(profile, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    existing = load_profile()
    if existing:
        print(f"\nExisting profile found at: {PROFILE_FILE}")
        overwrite = input("Overwrite it? (y/N): ").strip().lower()
        if overwrite != "y":
            show_profile(existing)
            print("\nProfile unchanged. Exiting.")
            exit(0)

    profile = collect_profile()
    save_profile(profile)
    show_profile(profile)
    print("\nNext step: run  python step2_search.py")
