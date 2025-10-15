"""
Views for user impersonation functionality
"""
from django.shortcuts import redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import User


@staff_member_required
def impersonate_user(request, user_id):
    """
    Start impersonating a user (superadmin only)
    """
    # Only superadmins can impersonate
    if not request.user.is_superuser:
        messages.error(request, "Only superadmins can impersonate users.")
        return redirect('admin:index')

    # Get the user to impersonate
    user_to_impersonate = get_object_or_404(User, id=user_id)

    # Don't allow impersonating yourself
    if user_to_impersonate.id == request.user.id:
        messages.warning(request, "You cannot impersonate yourself.")
        return redirect('admin:users_user_changelist')

    # Store impersonation in session
    request.session['impersonate_id'] = user_to_impersonate.id
    request.session['real_user_id'] = request.user.id

    messages.success(
        request,
        f'You are now viewing the system as: {user_to_impersonate.get_full_name() or user_to_impersonate.username} '
        f'({user_to_impersonate.get_role_display()})'
    )

    return redirect('admin:index')


@staff_member_required
def stop_impersonation(request):
    """
    Stop impersonating and return to real user
    """
    if 'impersonate_id' in request.session:
        del request.session['impersonate_id']
        if 'real_user_id' in request.session:
            del request.session['real_user_id']

        messages.info(request, 'You have stopped impersonating and returned to your account.')
    else:
        messages.info(request, 'You are not currently impersonating anyone.')

    return redirect('admin:index')
