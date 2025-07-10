from django.urls import path
from . import views
from .views import *
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', login_view, name="login"),
    path('login/', login_view, name="login"),
    path('register/', register_user, name="register"),
    path('verify/', verify_email, name='verify_email'),
    path('check_email/', check_email, name='check_email'),
    path('test-login/', views.test_login, name='test_login'),

    path("reset/", request_password_reset, name="password_reset"),
    path("reset/verify/", verify_reset_code, name="verify_reset_code"),
    path("reset/confirm/", set_new_password, name="set_new_password"),

    path('logout/', logout_view, name="logout"),
    path('profile/', profile_view, name="profile"),

    path('profile/upload-image/', upload_profile_image, name="upload_profile_image"),
    path('profile/images/', profile_images_json, name="profile_images_json"),
    path('profile/image/<uuid:pk>/delete/', delete_profile_image, name="delete_profile_image"),
    path('profile/image/<uuid:pk>/set-primary/', set_primary_image, name="set_primary_image"),

    # Chat
    path('messages/<uuid:user_id>/', messages_with, name='messages_with'),
    path("messages/", messages_home, name="messages_home"),
    path("messages/<uuid:user_id>/json/", messages_json, name="messages_json"),

    # Stripe: View plans and checkout
    path('upgrade/', upgrade_premium, name='upgrade_premium'),
    path("checkout/<str:plan>/", create_checkout_session, name="stripe_checkout"),
    path("stripe/success/", checkout_success, name="stripe_success"),
    path("stripe/cancel/", checkout_cancel, name="stripe_cancel"),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),

    path('user/', user_dashboard, name="user_dashboard"),
    path('admin_dashboard/', admin_dashboard, name="admin_dashboard"),
    path('likes/', likes_page, name="likes"),

    path('browse/', browse_one_profile, name='browse_one'),
    path('like/', like_profile, name='like_profile'),
    path('preferences/save/', save_preferences, name='save_preferences'),
    path("dislike/", dislike_profile, name="dislike_profile"),
    path('report/submit/', submit_report, name='submit_report'),
    path('admin_report_dashboard/', admin_report_dashboard, name='admin_report_dashboard'),
    path("admin_report/delete/<uuid:report_id>/", delete_report, name="delete_report"),
    path("toggle_report_status/<uuid:report_id>/", toggle_report_status, name="toggle_report_status"),
    path('admin_toggle_premium/<uuid:user_id>/', admin_toggle_premium, name='admin_toggle_premium'),
    path('admin_delete_user/<uuid:user_id>/', admin_delete_user, name='admin_delete_user'),
]
