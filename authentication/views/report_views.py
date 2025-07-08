# authentication/views/report_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import HttpResponseForbidden
from authentication.models import User, Report, Profile
from authentication.utils import log_action
import uuid

@login_required
def submit_report(request):
    if request.method == 'POST':
        reporter = request.user
        reported_user_id = request.POST.get('reported_user_id')
        reason = request.POST.get('reason', '').strip()
        description = request.POST.get('description', '').strip()

        if not reported_user_id or not reason:
            return HttpResponseForbidden("Missing required fields.")

        Report.objects.create(
            report_id=str(uuid.uuid4()),
            reporter_user_id=reporter,
            reported_user_id_id=reported_user_id,
            reason=reason,
            description=description,
            status='Pending',
            created_at=timezone.now()
        )

        log_action(reporter, f"Submitted report on user {reported_user_id}", "WARNING", request)
        return redirect('/browse/')

    return redirect('/browse/')

@user_passes_test(lambda u: u.role == 'admin')
@login_required
def admin_report_dashboard(request):
    reports = Report.objects.select_related('reporter_user_id', 'reported_user_id').order_by('-created_at')
    return render(request, 'pages/admin_report_dashboard.html', {'reports': reports})

@user_passes_test(lambda u: u.role == 'admin')
@login_required
def toggle_report_status(request, report_id):
    report = get_object_or_404(Report, report_id=report_id)
    if report.status == 'Resolved':
        report.status = 'Pending'
    else:
        report.status = 'Resolved'
    report.save(update_fields=['status'])

    log_action(request.user, f"Toggled status for report {report_id} to {report.status}", "INFO", request)
    return redirect('/admin/report-dashboard/')

@user_passes_test(lambda u: u.role == 'admin')
@login_required
def delete_report(request, report_id):
    report = get_object_or_404(Report, report_id=report_id)
    report.delete()

    log_action(request.user, f"Deleted report {report_id}", "CRITICAL", request)
    return redirect('/admin/report-dashboard/')
