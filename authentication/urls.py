from django.urls import path
from .views import *
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', login_view, name="login"),
    path('login/', login_view, name="login"),
    path('register/', register_user, name="register"),
    
    # ✅ Proper logout route
    path('logout/', LogoutView.as_view(next_page='login'), name="logout"),
    
    path('user/', user_dashboard, name="user_dashboard"),
    path('admin/', admin_dashboard, name="admin_dashboard"),

    path('browse/', views.browse_one_profile, name='browse_one'),
    path('like/', views.like_profile, name='like_profile'),
    path('preferences/save/', save_preferences, name='save_preferences'),
    path("dislike/", dislike_profile, name="dislike_profile"),

]
