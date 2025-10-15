"""
Context processors for user impersonation
"""


def impersonation_context(request):
    """
    Add impersonation status to all templates
    """
    context = {
        'is_impersonating': False,
        'impersonated_user': None,
        'real_user': None,
    }

    if hasattr(request, 'is_impersonating') and request.is_impersonating:
        context['is_impersonating'] = True
        context['impersonated_user'] = request.user
        if hasattr(request, 'real_user'):
            context['real_user'] = request.real_user

    return context
