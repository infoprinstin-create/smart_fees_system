from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [

    # =========================================================
    # LOGIN
    # =========================================================

    path(
    "login/",
    views.login_view,
    name="login"
    ),

    # =========================================================
    # USERS MANAGEMENT
    # =========================================================

        path(
        "users-management/",
        views.users_management,
        name="users_management"
    ),

        path(
        "users-management/create/",
        views.create_user,
        name="create_user"
    ),

    path(
    "users-management/<int:user_id>/edit/",
    views.edit_user,
    name="edit_user"
),

path(
    "users-management/<int:user_id>/password/",
    views.change_user_password,
    name="change_user_password"
),

path(
    "users-management/<int:user_id>/delete/",
    views.delete_user,
    name="delete_user"
),

    # =========================================================
    # SETTINGS
    # =========================================================

    path(
        "setting/",
        views.settings_view,
        name="settings"
    ),

    # =========================================================
    # LOGOUT
    # =========================================================

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    # =========================================================
    # STUDENTS
    # =========================================================

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

    # =========================================================
    # PAYMENTS
    # =========================================================

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

    # =========================================================
    # NORMAL FEE STRUCTURE
    # =========================================================

    path(
        "fees-structure/",
        views.fees_structure,
        name="fees_structure"
    ),

    path(
        "fees-structure/add/",
        views.add_fee_structure,
        name="add_fee_structure"
    ),

    # =========================================================
    # BILLS
    # =========================================================

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

    # =========================================================
    # REPORTS / CLASSES
    # =========================================================

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
        "classes/add/",
        views.add_class,
        name="add_class"
    ),

    path(
        "classes/<int:class_id>/",
        views.view_class,
        name="view_class"
    ),

    path(
        "classes/<int:class_id>/edit/",
        views.edit_class,
        name="edit_class"
    ),

    # =========================================================
    # BUS FEES
    # =========================================================

    path(
        "bus-fees/",
        views.bus_fees,
        name="bus_fees"
    ),

    # =========================================================
    # FEEDING FEES
    # =========================================================

    path(
        "feeding-fees/",
        views.feeding_fees,
        name="feeding_fees"
    ),

    # =========================================================
    # BUS + FEEDING STRUCTURE
    # =========================================================

    path(
        "bus-fee-structure/",
        views.bus_fee_structure,
        name="bus_fee_structure"
    ),

    # =========================================================
    # BUS STATUS
    # =========================================================

    path(
        "save-bus-status/",
        views.save_bus_status,
        name="save_bus_status"
    ),

    # =========================================================
    # FEEDING STATUS
    # =========================================================

    path(
        "save-feeding-status/",
        views.save_feeding_status,
        name="save_feeding_status"
    ),

    # =========================================================
    # HOME
    # =========================================================

    path(
        "",
        views.home,
        name="home"
    ),

    path(
    "export-excel/",
    views.export_excel,
    name="export_excel"
    ),

path(
    "payments/<int:payment_id>/receipt/",
    views.print_receipt,
    name="print_receipt"
),

    
]