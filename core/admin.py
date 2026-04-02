from django.contrib import admin
from .models import Document, StudyAsset

class StudyAssetInline(admin.TabularInline):
    """
    Allows viewing and managing StudyAssets directly from the Document admin page.
    """
    model = StudyAsset
    extra = 0
    fields = ('sqlite_asset_id', 'status', 'asset_type', 'content_preview', 'created_at')
    readonly_fields = ('created_at', 'content_preview')
    
    def content_preview(self, obj):
        if obj.content:
            return obj.content[:75] + '...' if len(obj.content) > 75 else obj.content
        return ""
    content_preview.short_description = "Content Preview"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'status', 'uploaded_at', 'updated_at', 'hash')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('filename', 'hash')
    readonly_fields = ('uploaded_at', 'updated_at')
    ordering = ('-uploaded_at',)
    inlines = [StudyAssetInline]
    
    fieldsets = (
        ('Document Info', {
            'fields': ('hash', 'filename', 'status')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(StudyAsset)
class StudyAssetAdmin(admin.ModelAdmin):
    list_display = ('sqlite_asset_id', 'document', 'status', 'asset_type', 'created_at')
    list_filter = ('status', 'asset_type', 'created_at')
    search_fields = ('sqlite_asset_id', 'document__filename', 'content')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Asset Information', {
            'fields': ('sqlite_asset_id', 'document', 'status', 'asset_type')
        }),
        ('Data', {
            'fields': ('content', 'image_paths')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
