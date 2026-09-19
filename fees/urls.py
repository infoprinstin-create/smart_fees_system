
from django.urls import path

from . import views


urlpatterns = [

    path(
        "setting/",
        views.settings_view,
        name="settings"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    path(
        "students/",
        views.students,
        name="students"
    ),

    path(
        "student-profile/<int:student_id>/",
        views.student_profile,
        name="student_profile"
    ),

    path(
    "student-profile/<int:student_id>/edit/",
    views.edit_student,
    name="edit_student"
    ),

    path(
        "add-student/",
        views.add_student,
        name="add_student"
    ),

    path(
        "payments/",
        views.payments,
        name="payments"
    ),

    path(
        "record-payment/",
        views.record_payment,
        name="record_payment"
    ),

    path(
    "student-payment-lookup/",
    views.student_payment_lookup,
    name="student_payment_lookup"
    ),

    path(
        "fees-structure/",
        views.fees_structure,
        name="fees_structure"
    ),

        path(
        "create-bill/",
        views.create_bill,
        name="create_bill"
    ),

    path(
    "bill-fee-lookup/",
    views.bill_fee_lookup,
    name="bill_fee_lookup"
    ),

    path(
      "fees-structure/add/",
       views.add_fee_structure,
       name="add_fee_structure"
    ),

    path(
        "reports/",
        views.reports,
        name="reports"
    ),

    path(
        "classes/",
        views.classes,
        name="classes"
    ),

    path(
        "",
        views.home,
        name="home"
    ),

    path("fees-structure/", views.fees_structure, name="fees_structure"),
    path("fees-structure/add/", views.add_fee_structure, name="add_fee_structure"),
    path("bus-fees/", views.bus_fees, name="bus_fees"),

    path(
    "bus-fee-structure/",
    views.bus_fee_structure,
    name="bus_fee_structure"
),

path(
    "save-bus-status/",
    views.save_bus_status,
    name="save_bus_status"
),

]


