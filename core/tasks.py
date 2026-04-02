from celery import shared_task
from django.db import transaction
from .models import Document
from .services import extract_with_llamaparse, chunk_to_sqlite, process_and_upload_assets

@shared_task
def process_ingestion_pipeline(file_hash, file_path):
    """
    The 3-Step Resilient Ingestion Pipeline.
    Manages state checkpoints and ensures safe retries.
    """
    print(f"[INFO] Starting ingestion pipeline for {file_hash}", flush=True)
    doc = Document.objects.get(hash=file_hash)

    # Step 1: LlamaParse Extraction
    if doc.status in ['PENDING', 'EXTRACTION_FAILED']:
        print(f"[INFO] Step 1: Starting LlamaParse extraction for {file_hash}", flush=True)
        doc.status = 'EXTRACTING'
        doc.save()
        try:
            # Checkpoint: Saving to media/[hash].json
            extract_with_llamaparse(file_hash, file_path)
            print(f"[SUCCESS] Step 1: Extraction completed for {file_hash}", flush=True)
        except Exception as e:
            print(f"[ERROR] Step 1: Extraction failed for {file_hash} - {str(e)}", flush=True)
            doc.status = 'EXTRACTION_FAILED'
            doc.save()
            return f"Failed Step 1: {str(e)}"

    # Step 2: Algorithmic Chunking & Asset Creation
    if doc.status in ['EXTRACTING', 'CHUNKING_FAILED']:
        print(f"[INFO] Step 2: Starting chunking for {file_hash}", flush=True)
        doc.status = 'CHUNKING'
        doc.save()
        try:
            # Atomic transaction checkpoint to DB
            with transaction.atomic():
                chunk_to_sqlite(file_hash, doc)
            print(f"[SUCCESS] Step 2: Chunking completed for {file_hash}", flush=True)
        except Exception as e:
            print(f"[ERROR] Step 2: Chunking failed for {file_hash} - {str(e)}", flush=True)
            doc.status = 'CHUNKING_FAILED'
            doc.save()
            return f"Failed Step 2: {str(e)}"

    # Step 3: Combined AI GraphRAG Extraction & Neo4j Promotion
    if doc.status in ['CHUNKING', 'UPLOAD_FAILED']:
        print(f"[INFO] Step 3: Starting AI Extraction & Neo4j Promotion for {file_hash}", flush=True)
        doc.status = 'UPLOADING'
        doc.save()
        try:
            # Safe Cypher MERGE operations loop with atomic per-asset states
            process_and_upload_assets(file_hash, doc)
            print(f"[SUCCESS] Step 3: Upload completed for {file_hash}", flush=True)
            
            # Document status is set to COMPLETED inside process_and_upload_assets, 
            # but we can refresh to verify it reached the end.
            doc.refresh_from_db()
        except Exception as e:
            print(f"[ERROR] Step 3: Upload failed for {file_hash} - {str(e)}", flush=True)
            doc.status = 'UPLOAD_FAILED'
            doc.save()
            return f"Failed Step 3: {str(e)}"

    print(f"[SUCCESS] Pipeline completed successfully for {file_hash}", flush=True)
    return f"Pipeline completed for {file_hash}"