from django.urls import path, include
#from django.contrib import admin
from django.views.generic import TemplateView
#from django.contrib.auth.decorators import login_required, user_passes_test
from authentication.views import user_dashboard
#from authentication.decorators import is_admin_user

#admin.site.login = user_passes_test(is_admin_user)(admin.site.login)

urlpatterns = [
    #path("admin/", admin.site.urls),
    path('', include('authentication.urls')),  # root path handles login/register/dashboard
    path('browse/', user_dashboard, name='browse'),
    path('messages/', TemplateView.as_view(template_name='pages/messages.html'), name='messages'),
    path('profile/', TemplateView.as_view(template_name='pages/profile.html'), name='profile'),
    path('likes/', TemplateView.as_view(template_name='pages/likes.html'), name='likes'),
]