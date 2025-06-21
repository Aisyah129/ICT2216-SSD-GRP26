from django.urls import path
from .views import login_view, register_user, user_dashboard, admin_dashboard, likes_page, profile_view, verify_email, request_password_reset, verify_reset_code, set_new_password, upgrade_premium, checkout_premium, upload_profile_image, profile_images_json, delete_profile_image, set_primary_image, messages_with, messages_home, messages_json, create_checkout_session, checkout_success, checkout_cancel, stripe_webhook
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', login_view, name="login"),
    path('login/', login_view, name="login"),
    path('register/', register_user, name="register"),
    path('verify/', verify_email, name='verify_email'),

    path("reset/", request_password_reset, name="password_reset"),
    path("reset/verify/", verify_reset_code, name="verify_reset_code"),
    path("reset/confirm/", set_new_password, name="set_new_password"),

    path('logout/', LogoutView.as_view(next_page='login'), name="logout"),
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
    path('admin/', admin_dashboard, name="admin_dashboard"),
    path('likes/', likes_page, name="likes"),

]
