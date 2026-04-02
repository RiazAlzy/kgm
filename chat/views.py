from django.shortcuts import render

def chat_interface(request):
    """
    Renders the foundational UI for the Chat application.
    All dynamic communication is handled via WebSockets & Alpine.js.
    """
    return render(request, 'chat.html')