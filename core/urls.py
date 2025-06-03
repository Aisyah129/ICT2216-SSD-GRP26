from django.urls import path, include
from django.views.generic import TemplateView

from authentication.views import user_dashboard

urlpatterns = [
    path('', include('authentication.urls')),  # root path handles login/register/dashboard
    path('browse/', user_dashboard, name='browse'),
    path('messages/', TemplateView.as_view(template_name='pages/messages.html'), name='messages'),
    path('profile/', TemplateView.as_view(template_name='pages/profile.html'), name='profile'),
    path('likes/', TemplateView.as_view(template_name='pages/likes.html'), name='likes'),
]
