# authentication/decorators.py
from functools import wraps
from django.shortcuts import redirect
from authentication.utils import has_permission

def user_only(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if has_permission(request.user, "edit_own_profile"):
            return view_func(request, *args, **kwargs)
        return redirect('admin_dashboard')
    return wrapper
