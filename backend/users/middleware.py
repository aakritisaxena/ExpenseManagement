"""
User Impersonation Middleware
Allows superadmins to view the system as another user
"""
from django.utils.deprecation import MiddlewareMixin


class ImpersonationMiddleware(MiddlewareMixin):
    """
    Middleware to handle user impersonation for superadmins.
    Stores the real superadmin in session and switches to impersonated user.
    """

    def process_request(self, request):
        if request.user.is_authenticated:
            # Check if there's an impersonation session
            impersonate_id = request.session.get('impersonate_id')

            if impersonate_id:
                # Store the real user if not already stored
                if not hasattr(request, '_cached_user'):
                    from users.models import User
                    try:
                        # Get the impersonated user
                        impersonated_user = User.objects.get(id=impersonate_id)

                        # Store the real superadmin
                        request.real_user = request.user

                        # Replace request.user with impersonated user
                        request.user = impersonated_user

                        # Add flag to indicate impersonation is active
                        request.is_impersonating = True
                    except User.DoesNotExist:
                        # Clear invalid impersonation
                        del request.session['impersonate_id']
                        request.is_impersonating = False
            else:
                request.is_impersonating = False
