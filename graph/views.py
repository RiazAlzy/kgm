import json
from django.shortcuts import render
from django.http import JsonResponse
from core.models import StudyAsset
from .services import fetch_graph_data

def graph_view(request):
    """Renders the base page container for the WebGL graph."""
    return render(request, 'graph.html')

def api_expand_node(request):
    """
    JSON API called by Vanilla JS force-graph to fetch nested nodes.
    Facilitates the RAM Garbage Collection pruning by returning exact slices.
    """
    node_id = request.GET.get('node_id')
    breadcrumbs_raw = request.GET.get('breadcrumbs', '[]')
    
    try:
        breadcrumbs = json.loads(breadcrumbs_raw)
    except json.JSONDecodeError:
        breadcrumbs =[]
    
    graph_data = fetch_graph_data(node_id, breadcrumbs)
    return JsonResponse(graph_data)

def asset_modal(request, sqlite_asset_ids):
    """
    HTMX Endpoint: Retrieves heavy text/images for ALL assets linked to a node.
    Accepts a comma-separated string of sqlite_asset_ids.
    """
    id_list = [aid.strip() for aid in sqlite_asset_ids.split(',')]
    assets = StudyAsset.objects.filter(sqlite_asset_id__in=id_list)
    return render(request, 'partials/asset_modal.html', {'assets': assets})