"""Bundle all required files into submission_drive_folder/ and create submission_drive_folder.zip.
Matches the official drive folder structure requested by the portal:
1. solver.py defining solve(n, m, budget, families, run)
2. Requirements file and run instructions (README.md, requirements.txt)
3. Logs: baselines, confusion matrix, accuracy vs budget
4. Technical report, PDF, max 3 pages (docs/report/technical-report.pdf)
5. AI-use disclosure, PDF, 1 page (docs/report/ai-use-disclosure.pdf)
6. Full repo zip (repo.zip) and github_link.txt
"""

import os
import shutil
import zipfile
from pathlib import Path


def create_submission_bundle():
    print("Creating submission bundle...")
    root = Path(".").resolve()
    dest = root / "submission_drive_folder"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # 1. solver.py
    shutil.copy2(root / "solver.py", dest / "solver.py")

    # 2. Requirements & README
    shutil.copy2(root / "requirements.txt", dest / "requirements.txt")
    shutil.copy2(root / "README.md", dest / "README.md")

    # 3. PDFs
    shutil.copy2(root / "docs" / "report" / "technical-report.pdf", dest / "technical-report.pdf")
    shutil.copy2(root / "docs" / "report" / "ai-use-disclosure.pdf", dest / "ai-use-disclosure.pdf")

    # 4. Logs directory
    logs_dest = dest / "logs"
    shutil.copytree(root / "logs", logs_dest)

    # 5. Full repo zip
    repo_zip_path = dest / "repo.zip"
    print("Creating repo.zip...")
    with zipfile.ZipFile(repo_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in root.rglob("*"):
            rel = file.relative_to(root)
            # Exclude virtual env, git, and submission bundles
            parts = rel.parts
            if any(p in parts for p in [".venv", ".git", ".pytest_cache", "__pycache__", "submission_drive_folder"]):
                continue
            if file.is_file():
                zipf.write(file, rel)

    # 6. Overall submission zip (for easy upload to Google Drive)
    overall_zip_path = root / "submission_drive_folder.zip"
    print(f"Creating {overall_zip_path.name}...")
    with zipfile.ZipFile(overall_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in dest.rglob("*"):
            rel = file.relative_to(dest)
            if file.is_file():
                zipf.write(file, rel)

    print(f"SUCCESS: Submission folder prepared at: {dest}")
    print(f"SUCCESS: Submission ZIP prepared at:    {overall_zip_path}")


if __name__ == "__main__":
    create_submission_bundle()
