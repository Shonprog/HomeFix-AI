import argparse
import json
import os
from pathlib import Path

import requests

# Standalone script (not run through Streamlit) -> configured via env var,
# not st.secrets. Set before running:
#   PowerShell: $env:N8N_MANUAL_UPLOAD_URL = "https://.../webhook/homefix/manuals"
WEBHOOK_URL = os.environ.get("N8N_MANUAL_UPLOAD_URL")
if not WEBHOOK_URL:
    raise SystemExit(
        "N8N_MANUAL_UPLOAD_URL environment variable is not set. "
        "Set it to the n8n manuals-upload webhook URL before running this script."
    )

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "manifest.json"
DOCUMENTS_DIR = ROOT / "documents"

if not MANIFEST_PATH.is_file():
    raise SystemExit(f"manifest.json not found at: {MANIFEST_PATH}")

if not DOCUMENTS_DIR.is_dir():
    raise SystemExit(f"documents/ folder not found at: {DOCUMENTS_DIR}")

parser = argparse.ArgumentParser()
parser.add_argument(
    "--limit",
    type=int,
    default=None,
    help="Upload only the first N documents from manifest.json.",
)
parser.add_argument(
    "--file",
    type=str,
    default=None,
    help="Upload only the manifest entry whose filename basename matches this value.",
)
args = parser.parse_args()

with open(MANIFEST_PATH, "r", encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)

documents = manifest.get("documents", [])

if args.file is not None:
    documents = [
        d for d in documents if Path(d.get("filename", "")).name == args.file
    ]
    if not documents:
        raise SystemExit(
            f"No manifest entry found with filename matching: {args.file}"
        )
elif args.limit is not None:
    documents = documents[: args.limit]

total = len(documents)

success_count = 0
failed_count = 0

for index, document in enumerate(documents, start=1):
    manufacturer = document.get("manufacturer", "")
    category = document.get("category", "")
    model_family = document.get("model_family", "")
    document_type = document.get("document_type", "")
    language = document.get("language", "")
    filename = document.get("filename", "")

    label = f"[{index}/{total}] {manufacturer} | {category} | {model_family}"
    print(label)

    if not filename:
        print("SKIPPED - missing filename in manifest entry")
        failed_count += 1
        continue

    pdf_path = DOCUMENTS_DIR / filename

    if not pdf_path.is_file():
        print(f"SKIPPED - file not found: documents/{filename}")
        failed_count += 1
        continue

    source_name = Path(filename).name

    form_data = {
        "manufacturer": manufacturer,
        "device_type": category,
        "model": model_family,
        "document_type": document_type,
        "language": language,
        "source": source_name,
    }

    try:
        with open(pdf_path, "rb") as pdf_file:
            files = {
                "data": (
                    source_name,
                    pdf_file,
                    "application/pdf",
                )
            }

            response = requests.post(
                WEBHOOK_URL,
                data=form_data,
                files=files,
                timeout=900,
            )
            response.raise_for_status()

        print("OK")
        success_count += 1
    except (requests.RequestException, OSError) as exc:
        print(f"FAILED - {type(exc).__name__}: {exc}")
        failed_count += 1

print()
print("===========================")
print("Upload finished")
print("===============")
print()
print(f"Success: {success_count}")
print(f"Failed: {failed_count}")
