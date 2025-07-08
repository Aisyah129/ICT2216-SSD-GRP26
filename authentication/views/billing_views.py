# authentication/views/billing_views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.conf import settings
import stripe, json, datetime
from authentication.models import User, BillingEvent
from authentication.utils import log_action

stripe.api_key = settings.STRIPE_SECRET_KEY

def is_active_sub(user):
    try:
        latest = BillingEvent.objects.filter(user_id=user.user_id, status='success').latest('timestamp')
        return latest.expiry_at and latest.expiry_at > datetime.datetime.now(datetime.timezone.utc)
    except BillingEvent.DoesNotExist:
        return False

@login_required
def upgrade_premium(request):
    user = request.user
    has_active = is_active_sub(user)
    return render(request, 'pages/upgrade_premium.html', {'is_premium': has_active})

@login_required
def create_checkout_session(request):
    user = request.user

    try:
        checkout_session = stripe.checkout.Session.create(
            success_url=settings.DOMAIN + '/upgrade-success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=settings.DOMAIN + '/upgrade-failed',
            mode='payment',
            customer_email=user.email,
            payment_method_types=['card'],
            line_items=[{
                'quantity': 1,
                'price_data': {
                    'currency': 'sgd',
                    'unit_amount': 3900,
                    'product_data': {
                        'name': 'Premium Membership (30 Days)'
                    }
                }
            }],
            metadata={'user_id': str(user.user_id)}
        )

        return JsonResponse({'id': checkout_session.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
    except Exception as e:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')
        email = session.get('customer_email')
        amount_total = session.get('amount_total', 0)

        BillingEvent.objects.create(
            user_id=user_id,
            email=email,
            event_id=session['id'],
            amount=amount_total / 100.0,
            status='success',
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            expiry_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        )

    return HttpResponse(status=200)

@login_required
def upgrade_success(request):
    request.user.is_premium = True
    request.user.save(update_fields=['is_premium'])
    log_action(request.user, "Successfully upgraded to Premium", "INFO", request)
    return render(request, 'pages/upgrade_success.html')

@login_required
def upgrade_failed(request):
    log_action(request.user, "Failed or canceled premium upgrade", "WARNING", request)
    return render(request, 'pages/upgrade_failed.html')
