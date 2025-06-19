from django.urls import path
from .views import login_view, register_user, user_dashboard, admin_dashboard, likes_page
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', login_view, name="login"),
    path('login/', login_view, name="login"),
    path('register/', register_user, name="register"),
    
    # ✅ Proper logout route
    path('logout/', LogoutView.as_view(next_page='login'), name="logout"),
    
    path('user/', user_dashboard, name="user_dashboard"),
    path('admin/', admin_dashboard, name="admin_dashboard"),

    path('likes/', likes_page, name="likes"),
]
