import hashlib
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Document
from .tasks import process_ingestion_pipeline
import os

def core_index(request):
    """Renders the upload UI extending base.html"""
    return render(request, 'core.html')

def upload_document(request):
    """Handles file uploads, hashing, state checking, and task delegation."""
    print(f"--- [DEBUG] Request Method: {request.method} ---", flush=True)
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        print(f"--- [DEBUG] File Found: {file.name} ---", flush=True)
        
        # 1. Upload & Granular State Check (Hash File)
        file_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0) # Reset pointer
        
        doc, created = Document.objects.get_or_create(
            hash=file_hash,
            defaults={'filename': file.name, 'status': 'PENDING'}
        )
        
        # Check Pipeline Status to Reject or Retry
        in_progress_states =['EXTRACTING', 'CHUNKING', 'UPLOADING']
        
        if not created:
            if doc.status == 'COMPLETED':
                print(f"[ERROR] Document already ingested: {file.name} ({file_hash})", flush=True)
                return JsonResponse({'message': 'Document already ingested.', 'hash': file_hash}, status=409)
            if doc.status in in_progress_states:
                print(f"[INFO] Document is currently processing: {file.name} ({file_hash})", flush=True)
                return JsonResponse({'message': 'Document is currently processing.', 'hash': file_hash}, status=409)
            print(f"[DEBUG] Retrying delegation for document in state: {doc.status}", flush=True)

        # Save raw file
        ext = os.path.splitext(file.name)[1].lower()
        
        from django.conf import settings
        if not os.path.exists(settings.MEDIA_ROOT):
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            
        file_path = os.path.join(settings.MEDIA_ROOT, f"raw_{file_hash}{ext}")
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        print(f"[SUCCESS] File saved for hash: {file_hash}. Proceeding to delegation...", flush=True)

        # 2. Task Delegation (Celery)
        print(f"[DEBUG] Calling {process_ingestion_pipeline.name}.delay() for {file_hash}...", flush=True)
        try:
            task = process_ingestion_pipeline.delay(file_hash, file_path)
            print(f"[INFO] Task delegation returned task_id: {task.id}", flush=True)
            print(f"[INFO] Task delegated successfully for processing: {file_hash}", flush=True)
        except Exception as e:
            import traceback
            print(f"[ERROR] Task delegation failed for {file_hash}: {str(e)}", flush=True)
            traceback.print_exc()
            return JsonResponse({'error': 'Failed to start processing.'}, status=500)

        return JsonResponse({'message': 'Processing started.', 'hash': file_hash}, status=202)
        
    print("[ERROR] Invalid upload request.", flush=True)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def document_progress(request, file_hash):
    """HTMX endpoint to poll/return the partial UI for progress."""
    doc = get_object_or_404(Document, hash=file_hash)
    return render(request, 'partials/upload_progress.html', {'document': doc})