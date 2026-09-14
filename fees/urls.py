from django.urls import path
from . import views
urlpatterns = [
    path("setting/", views.settings_view, name="settings"),
    path("logout/", views.logout_view, name="logout"),
    path("students/", views.students, name="students"),
    path("student-profile/", views.student_profile, name="student_profile"),
    path("add-student/", views.add_student, name="add_student"),
    path("payments/", views.payments, name="payments"),
    path("", views.home, name="home"),
    path("fees-structure/", views.fees_structure, name="fees_structure"),
    path("reports/", views.reports, name="reports"),
    path("classes/", views.classes, name="classes"),
    path("record-payment/", views.record_payment, name="record_payment"),
]