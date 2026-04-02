import uuid
from django.db import models

class Document(models.Model):
    STATUS_CHOICES =[
        ('PENDING', 'Pending Initialization'),
        ('EXTRACTING', 'EXTRACTING (LlamaParse)'),
        ('EXTRACTION_FAILED', 'EXTRACTION_FAILED'),
        ('CHUNKING', 'CHUNKING'),
        ('CHUNKING_FAILED', 'CHUNKING_FAILED'),
        ('UPLOADING', 'UPLOADING'),
        ('UPLOAD_FAILED', 'UPLOAD_FAILED'),
        ('COMPLETED', 'COMPLETED'),
    ]

    hash = models.CharField(max_length=64, unique=True, primary_key=True, help_text="SHA-256 hash of the file content.")
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.filename} ({self.status})"

class StudyAsset(models.Model):
    """
    Independent knowledge chunks mapping directly to Neo4j nodes.
    """
    ASSET_STATUS_CHOICES = [
        ('EXTRACTED', 'EXTRACTED'),
        ('UPLOADED', 'UPLOADED'),
    ]
    sqlite_asset_id = models.CharField(max_length=255, primary_key=True)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="assets", null=True)
    status = models.CharField(max_length=20, default='EXTRACTED', help_text="EXTRACTED or UPLOADED")
    asset_type = models.CharField(max_length=50, help_text="'text', 'table'")
    content = models.TextField(help_text="Markdown text, or table")
    created_at = models.DateTimeField(auto_now_add=True)

    
    image_paths = models.JSONField(default=list, blank=True, help_text="List of associated image filenames")

    def __str__(self):
        return f"{self.asset_type} Asset: {self.sqlite_asset_id}"