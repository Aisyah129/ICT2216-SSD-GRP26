# authentication/views/admin_views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from authentication.models import User, Match, Like, Report, LogEvent, Profile

@user_passes_test(lambda u: u.role == 'admin')
@login_required
def admin_dashboard(request):
    total_users = User.objects.count()
    total_premium = User.objects.filter(is_premium=True).count()
    total_matches = Match.objects.count()
    total_likes = Like.objects.filter(like_status='liked').count()
    total_passes = Like.objects.filter(like_status='passed').count()
    total_reports = Report.objects.count()
    total_logs = LogEvent.objects.count()

    top_reported_users = (Report.objects
        .values('reported_user_id__email')
        .annotate(report_count=Count('report_id'))
        .order_by('-report_count')[:5])

    return render(request, 'pages/admin_dashboard.html', {
        'total_users': total_users,
        'total_premium': total_premium,
        'total_matches': total_matches,
        'total_likes': total_likes,
        'total_passes': total_passes,
        'total_reports': total_reports,
        'total_logs': total_logs,
        'top_reported_users': top_reported_users
    })

@user_passes_test(lambda u: u.role == 'admin')
@login_required
def admin_logs_view(request):
    logs = LogEvent.objects.select_related('user_id').order_by('-timestamp')[:100]
    return render(request, 'pages/admin_logs.html', {'logs': logs})
