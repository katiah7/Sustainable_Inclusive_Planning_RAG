import csv
import os
import time

import requests

MAX_FILE_SIZE = 10 * 1024 * 1024
TARGET_DOCUMENTS = 45

documents_folder = "data/raw"

search_terms = [
    "urban planning Kenya",
    "climate resilient urban planning Kenya",
    "climate adaptation urban planning Kenya",
    "inclusive urban planning Kenya",
    "urban development Kenya climate",
    "urban housing Kenya climate resilience",
    "informal settlements Kenya urban planning",
    "urban infrastructure Kenya climate resilience",
    "urban flooding Kenya",
    "urban resilience Kenya",
]

urban_planning_keywords = [
    "urban planning",
    "urban development",
    "spatial planning",
    "land use planning",
    "urban development plan",
    "city development",
    "urban master plan",
    "urban upgrading",
]

climate_keywords = [
    "climate change",
    "climate resilience",
    "climate adaptation",
    "climate risk",
    "climate vulnerability",
    "flood risk",
    "urban flooding",
    "drought",
    "heat",
    "disaster risk",
]

inclusion_keywords = [
    "informal settlements",
    "informal settlement",
    "urban poverty",
    "social inclusion",
    "equity",
    "vulnerable communities",
    "community participation",
    "public participation",
    "inclusive urban",
]

excluded_types = [
    "procurement plan",
    "procurement notice",
    "procurement",
    "financial statement",
    "audit report",
    "contract",
    "disbursement",
    "legal agreement",
    "loan agreement",
    "financing agreement",
]

kenya_keywords = [
    "kenya",
    "nairobi",
    "mombasa",
    "kisumu",
    "nakuru",
    "eldoret",
    "kiambu",
    "machakos",
    "kakamega",
]

unique_documents = {}

for search_term in search_terms:
    url = "https://search.worldbank.org/api/v3/wds"

    params = {"format": "json", "qterm": search_term, "rows": 50}

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    documents = data["documents"]

    for document_id, document in documents.items():
        if document_id not in unique_documents:
            unique_documents[document_id] = document


print("Unique documents:", len(unique_documents))

relevant_documents = []

for document_id, document in unique_documents.items():
    title = document.get("display_title", "")
    region = document.get("admreg", "")
    country = document.get("count", "")
    theme = document.get("theme", "")
    subtopic = document.get("subtopic", "")
    document_type = document.get("docty", "")
    document_date = document.get("docdt", "")

    keywords = document.get("keywd", {})

    keyword_text = " ".join(item.get("keywd", "") for item in keywords.values())

    searchable_text = " ".join(
        [title, region, country, theme, subtopic, keyword_text]
    ).lower()

    is_kenya = any(keyword in searchable_text for keyword in kenya_keywords)

    is_urban_planning = any(
        keyword in searchable_text for keyword in urban_planning_keywords
    )

    is_climate = any(keyword in searchable_text for keyword in climate_keywords)

    is_inclusion = any(keyword in searchable_text for keyword in inclusion_keywords)

    is_excluded_type = any(
        excluded in document_type.lower() for excluded in excluded_types
    )

    is_recent = document_date >= "2015-01-01"

    if (
        is_kenya
        and is_urban_planning
        and (is_climate or is_inclusion)
        and is_recent
        and not is_excluded_type
    ):
        relevant_documents.append({"id": document_id, "document": document})


print()
print("RELEVANT CANDIDATES")
print("Candidates found:", len(relevant_documents))

os.makedirs(documents_folder, exist_ok=True)

metadata_rows = []

print()
print("STARTING DOWNLOADS")

successful_downloads = 0
skipped_large = 0
failed_downloads = 0
no_pdf_url = 0

for item in relevant_documents:
    if successful_downloads >= TARGET_DOCUMENTS:
        break

    document_id = item["id"]
    document = item["document"]

    title = document.get("display_title", "")
    date = document.get("docdt", "")
    document_type = document.get("docty", "")
    pdf_url = document.get("pdfurl", "")

    filename = f"{document_id}.pdf"
    filepath = os.path.join(documents_folder, filename)

    print()
    print(f"[{successful_downloads + 1}/{TARGET_DOCUMENTS}] {document_id}")

    if os.path.exists(filepath):
        file_size = os.path.getsize(filepath)

        if file_size < MAX_FILE_SIZE:
            print("Already downloaded - under 10 MB")

            successful_downloads += 1

            metadata_rows.append(
                {
                    "id": document_id,
                    "title": title,
                    "date": date,
                    "type": document_type,
                    "pdf_url": pdf_url,
                    "filename": filename,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "status": "already existed",
                }
            )

            continue

        else:
            print("Existing file is over 10 MB - deleting")

            os.remove(filepath)

    if not pdf_url:
        print("No PDF URL - skipping")

        no_pdf_url += 1

        metadata_rows.append(
            {
                "id": document_id,
                "title": title,
                "date": date,
                "type": document_type,
                "pdf_url": "",
                "filename": "",
                "size_mb": "",
                "status": "no PDF URL",
            }
        )

        continue

    try:
        pdf_response = requests.get(pdf_url, timeout=60)

        pdf_response.raise_for_status()

        file_size = len(pdf_response.content)

        if file_size >= MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)

            print(f"Too large: {size_mb:.2f} MB - skipping")

            skipped_large += 1

            metadata_rows.append(
                {
                    "id": document_id,
                    "title": title,
                    "date": date,
                    "type": document_type,
                    "pdf_url": pdf_url,
                    "filename": "",
                    "size_mb": round(size_mb, 2),
                    "status": "skipped - over 10 MB",
                }
            )

            continue

        with open(filepath, "wb") as pdf_file:
            pdf_file.write(pdf_response.content)

        size_mb = file_size / (1024 * 1024)

        print(f"Downloaded: {filename} ({size_mb:.2f} MB)")

        successful_downloads += 1

        metadata_rows.append(
            {
                "id": document_id,
                "title": title,
                "date": date,
                "type": document_type,
                "pdf_url": pdf_url,
                "filename": filename,
                "size_mb": round(size_mb, 2),
                "status": "downloaded",
            }
        )

    except requests.RequestException as error:
        print("Download failed:", error)

        failed_downloads += 1

        metadata_rows.append(
            {
                "id": document_id,
                "title": title,
                "date": date,
                "type": document_type,
                "pdf_url": pdf_url,
                "filename": "",
                "size_mb": "",
                "status": "failed",
            }
        )

    time.sleep(0.5)

csv_filename = "documents_metadata.csv"

with open(csv_filename, "w", newline="", encoding="utf-8") as csv_file:
    fieldnames = [
        "id",
        "title",
        "date",
        "type",
        "pdf_url",
        "filename",
        "size_mb",
        "status",
    ]

    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(metadata_rows)

print()
print("DOWNLOAD COMPLETE")

print("Relevant candidates:", len(relevant_documents))
print("Documents downloaded/available:", successful_downloads)
print("Skipped over 10 MB:", skipped_large)
print("No PDF URL:", no_pdf_url)
print("Failed:", failed_downloads)

print()
print("Target:", TARGET_DOCUMENTS)
print("Maximum file size: < 10 MB")
print("PDFs saved in:", documents_folder)
print("Metadata saved in:", csv_filename)
