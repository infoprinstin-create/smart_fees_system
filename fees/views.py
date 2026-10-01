
from functools import wraps
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.http import JsonResponse
from django.db import models
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.contrib import messages
from django.db.models import Sum
from collections import defaultdict
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Student,
    SchoolSettings,
    SchoolClass,
    FeeStructure,
    Payment,
    Bill,
    BusFeeStructure,
    UserProfile,
    BusFeeRecord,
    FeedingFeeStructure,
    FeedingFeeRecord,
)


# =========================================================
# ROLE ACCESS CONTROL
# =========================================================

def redirect_user_by_role(request):

    # Administrator / Superuser
    if request.user.is_superuser:
        return redirect("home")

    try:
        role = request.user.profile.role

    except UserProfile.DoesNotExist:
        logout(request)
        return redirect("login")

    # School Fees
    if role == "school_fees":
        return redirect("students")

    # Bus Fee
    if role == "bus_fee":
        return redirect("bus_fees")

    # Feeding Fee
    if role == "feeding_fee":
        return redirect("feeding_fees")

    # Administrator role stored in profile
    if role == "administrator":
        return redirect("home")

    # Unknown role
    logout(request)

    return redirect("login")


def role_required(*allowed_roles):

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            # Administrator has full access
            if request.user.is_superuser:
                return view_func(
                    request,
                    *args,
                    **kwargs
                )

            try:
                user_role = request.user.profile.role

            except UserProfile.DoesNotExist:
                logout(request)
                return redirect("login")

            # Check permission
            if user_role not in allowed_roles:

                messages.error(
                    request,
                    "You do not have permission to access this page."
                )

                return redirect_user_by_role(request)

            return view_func(
                request,
                *args,
                **kwargs
            )

        return wrapper

    return decorator


# =========================================================
# LOGOUT
# =========================================================

@login_required
def logout_view(request):

    logout(request)

    return redirect("login")


# =========================================================
# LOGIN
# =========================================================

def login_view(request):

    if request.user.is_authenticated:
        return redirect_user_by_role(request)

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(
                request,
                user
            )

            return redirect_user_by_role(request)

        return render(
            request,
            "registration/login.html",
            {
                "login_error": True,
            }
        )

    return render(
        request,
        "registration/login.html"
    )


# =========================================================
# SETTINGS
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def settings_view(request):

    settings = SchoolSettings.objects.first()

    if not settings:
        settings = SchoolSettings.objects.create()

    if request.method == "POST":

        # =====================================================
        # CHANGE ADMIN PASSWORD
        # =====================================================

        if request.POST.get("change_password") == "1":

            current_password = request.POST.get(
                "current_password",
                ""
            )

            new_password = request.POST.get(
                "new_password",
                ""
            )

            confirm_password = request.POST.get(
                "confirm_password",
                ""
            )

            # CHECK CURRENT PASSWORD
            if not request.user.check_password(
                current_password
            ):

                messages.error(
                    request,
                    "Current password is incorrect."
                )

                return redirect("settings")

            # CHECK NEW PASSWORD
            if not new_password:

                messages.error(
                    request,
                    "Please enter a new password."
                )

                return redirect("settings")

            # CHECK PASSWORD MATCH
            if new_password != confirm_password:

                messages.error(
                    request,
                    "New password and confirmation password do not match."
                )

                return redirect("settings")

            # CHECK PASSWORD LENGTH
            if len(new_password) < 8:

                messages.error(
                    request,
                    "Password must be at least 8 characters long."
                )

                return redirect("settings")

            # CHANGE PASSWORD
            request.user.set_password(
                new_password
            )

            request.user.save()

            messages.success(
                request,
                "Your password has been changed successfully."
            )

            # Keep the administrator logged in
            from django.contrib.auth import update_session_auth_hash

            update_session_auth_hash(
                request,
                request.user
            )

            return redirect("settings")


        # =====================================================
        # SCHOOL SETTINGS
        # =====================================================

        settings.school_name = request.POST.get(
            "school_name",
            ""
        ).strip()

        settings.address = request.POST.get(
            "address",
            ""
        ).strip()

        settings.phone = request.POST.get(
            "phone",
            ""
        ).strip()

        settings.email = request.POST.get(
            "email",
            ""
        ).strip()

        settings.academic_year = request.POST.get(
            "academic_year",
            ""
        ).strip()

        settings.school_motto = request.POST.get(
            "school_motto",
            ""
        ).strip()


        # =====================================================
        # SCHOOL LOGO
        # =====================================================

        uploaded_logo = request.FILES.get(
            "school_logo"
        )

        if uploaded_logo:

            import os
            import cloudinary

            cloudinary_url = os.environ.get(
                "CLOUDINARY_URL"
            )

            cloudinary.config(
                cloudinary_url=cloudinary_url,
                secure=True
            )

            settings.logo = uploaded_logo


        settings.save()

        messages.success(
            request,
            "School settings have been updated successfully."
        )

        return redirect("settings")


    return render(
        request,
        "fees/settings.html",
        {
            "school_settings": settings
        }
    )

# =========================================================
# STUDENTS
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def students(request):

    students = Student.objects.all().order_by(
        "-date_registered"
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        students = students.filter(
            models.Q(
                first_name__icontains=search
            )
            |
            models.Q(
                last_name__icontains=search
            )
            |
            models.Q(
                student_id__icontains=search
            )
            |
            models.Q(
                registration_number__icontains=search
            )
        )

    # =====================================================
    # CLASS FILTER
    # =====================================================

    selected_class = request.GET.get(
        "class",
        ""
    ).strip()

    if selected_class:

        students = students.filter(
            student_class=selected_class
        )

    # =====================================================
    # STATUS FILTER
    # =====================================================

    selected_status = request.GET.get(
        "status",
        ""
    ).strip()

    if selected_status:

        students = students.filter(
            status=selected_status
        )

    # =====================================================
    # GENDER FILTER
    # =====================================================

    selected_gender = request.GET.get(
        "gender",
        ""
    ).strip()

    if selected_gender:

        students = students.filter(
            gender=selected_gender
        )

    # =====================================================
    # CALCULATE FEES FOR EACH STUDENT
    # =====================================================

    for student in students:

        # -------------------------------------------------
        # FEE STRUCTURE
        # -------------------------------------------------

        student.fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()

        # -------------------------------------------------
        # FIND LATEST BILL
        # -------------------------------------------------

        student.bill = Bill.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).order_by(
            "-id"
        ).first()

        # -------------------------------------------------
        # TOTAL FEE
        # -------------------------------------------------

        if student.bill:

            # Use discounted amount from the bill
            student.total_fee = (
                student.bill.amount_due
            )

        elif student.fee_structure:

            # No bill yet — use original fee
            student.total_fee = (
                student.fee_structure.total_fee
            )

        else:

            student.total_fee = 0

        # -------------------------------------------------
        # TOTAL PAID
        # -------------------------------------------------

        student.total_paid = Payment.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        # -------------------------------------------------
        # BALANCE
        # -------------------------------------------------

        student.calculated_balance = (
            student.total_fee -
            student.total_paid
        )

        if student.calculated_balance < 0:

            student.calculated_balance = 0

        # -------------------------------------------------
        # FEE STATUS
        # -------------------------------------------------

        if student.total_fee <= 0:

            student.calculated_fee_status = "Pending"

        elif student.total_paid >= student.total_fee:

            student.calculated_fee_status = "Paid"

        else:

            student.calculated_fee_status = "Pending"

    # =====================================================
    # CLASS OPTIONS
    # =====================================================

    classes = Student.objects.values_list(
        "student_class",
        flat=True
    ).distinct().order_by(
        "student_class"
    )

    # =====================================================
    # STATISTICS
    # =====================================================

    all_students = Student.objects.all()

    total_students = all_students.count()

    active_students = all_students.filter(
        status="Active"
    ).count()

    inactive_students = all_students.filter(
        status="Inactive"
    ).count()

    # =====================================================
    # CURRENT ACADEMIC YEAR
    # =====================================================

    school_settings = SchoolSettings.objects.first()

    if school_settings:

        current_academic_year = (
            school_settings.academic_year
        )

    else:

        current_academic_year = "2026/2027"

    new_admissions = all_students.filter(
        academic_year=current_academic_year
    ).count()

    # =====================================================
    # RETURN PAGE
    # =====================================================

    return render(
        request,
        "fees/students.html",
        {
            "students": students,
            "total_students": total_students,
            "active_students": active_students,
            "inactive_students": inactive_students,
            "new_admissions": new_admissions,
            "classes": classes,
            "search": search,
            "selected_class": selected_class,
            "selected_status": selected_status,
            "selected_gender": selected_gender,
        }
    )


# =========================================================
# STUDENTS
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def students(request):

    students = Student.objects.all().order_by(
        "-date_registered"
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        students = students.filter(
            models.Q(
                first_name__icontains=search
            )
            |
            models.Q(
                last_name__icontains=search
            )
            |
            models.Q(
                student_id__icontains=search
            )
            |
            models.Q(
                registration_number__icontains=search
            )
        )

    # =====================================================
    # CLASS FILTER
    # =====================================================

    selected_class = request.GET.get(
        "class",
        ""
    ).strip()

    if selected_class:

        students = students.filter(
            student_class=selected_class
        )

    # =====================================================
    # STATUS FILTER
    # =====================================================

    selected_status = request.GET.get(
        "status",
        ""
    ).strip()

    if selected_status:

        students = students.filter(
            status=selected_status
        )

    # =====================================================
    # GENDER FILTER
    # =====================================================

    selected_gender = request.GET.get(
        "gender",
        ""
    ).strip()

    if selected_gender:

        students = students.filter(
            gender=selected_gender
        )

    # =====================================================
    # CALCULATE FEES FOR EACH STUDENT
    # =====================================================

    for student in students:

        # -------------------------------------------------
        # FEE STRUCTURE
        # -------------------------------------------------

        student.fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()

        # -------------------------------------------------
        # FIND LATEST BILL
        # -------------------------------------------------

        student.bill = Bill.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).order_by(
            "-id"
        ).first()

        # -------------------------------------------------
        # TOTAL FEE
        # -------------------------------------------------

        if student.bill:

            # Use discounted amount from the bill
            student.total_fee = (
                student.bill.amount_due
            )

        elif student.fee_structure:

            # No bill yet — use original fee
            student.total_fee = (
                student.fee_structure.total_fee
            )

        else:

            student.total_fee = 0

        # -------------------------------------------------
        # TOTAL PAID
        # -------------------------------------------------

        student.total_paid = Payment.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        # -------------------------------------------------
        # BALANCE
        # -------------------------------------------------

        student.calculated_balance = (
            student.total_fee -
            student.total_paid
        )

        if student.calculated_balance < 0:

            student.calculated_balance = 0

        # -------------------------------------------------
        # FEE STATUS
        # -------------------------------------------------

        if student.total_fee <= 0:

            student.calculated_fee_status = "Pending"

        elif student.total_paid >= student.total_fee:

            student.calculated_fee_status = "Paid"

        else:

            student.calculated_fee_status = "Pending"

    # =====================================================
    # CLASS OPTIONS
    # =====================================================

    classes = Student.objects.values_list(
        "student_class",
        flat=True
    ).distinct().order_by(
        "student_class"
    )

    # =====================================================
    # STATISTICS
    # =====================================================

    all_students = Student.objects.all()

    total_students = all_students.count()

    active_students = all_students.filter(
        status="Active"
    ).count()

    inactive_students = all_students.filter(
        status="Inactive"
    ).count()

    # =====================================================
    # CURRENT ACADEMIC YEAR
    # =====================================================

    school_settings = SchoolSettings.objects.first()

    if school_settings:

        current_academic_year = (
            school_settings.academic_year
        )

    else:

        current_academic_year = "2026/2027"

    new_admissions = all_students.filter(
        academic_year=current_academic_year
    ).count()

    # =====================================================
    # RETURN PAGE
    # =====================================================

    return render(
        request,
        "fees/students.html",
        {
            "students": students,
            "total_students": total_students,
            "active_students": active_students,
            "inactive_students": inactive_students,
            "new_admissions": new_admissions,
            "classes": classes,
            "search": search,
            "selected_class": selected_class,
            "selected_status": selected_status,
            "selected_gender": selected_gender,
        }
    )

# =========================================================
# EDIT STUDENT
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def edit_student(request, student_id):

    student = get_object_or_404(
        Student,
        id=student_id
    )

    if request.method == "POST":

        student.first_name = request.POST.get(
            "first_name",
            ""
        ).strip()

        student.last_name = request.POST.get(
            "last_name",
            ""
        ).strip()

        student.student_id = request.POST.get(
            "student_id",
            ""
        ).strip()

        student.registration_number = (
            request.POST.get(
                "registration_number",
                ""
            ).strip()
            or None
        )

        student.date_of_birth = (
            request.POST.get(
                "date_of_birth"
            )
            or None
        )

        student.student_class = request.POST.get(
            "class_name",
            ""
        ).strip()

    
        student.academic_year = request.POST.get(
            "academic_year",
            ""
        ).strip()

        student.gender = (
            request.POST.get(
                "gender",
                ""
            ).title()
        )

        student.parent_name = request.POST.get(
            "parent_name",
            ""
        ).strip()

        student.parent_contact = request.POST.get(
            "parent_contact",
            ""
        ).strip()

        student.address = request.POST.get(
            "address",
            ""
        ).strip()

        student.additional_information = request.POST.get(
            "additional_information",
            ""
        ).strip()

        student.status = request.POST.get(
            "status",
            "Active"
        )

        # Only replace photo when a new one is selected
        if request.FILES.get("student_photo"):

            student.photo = request.FILES.get(
                "student_photo"
            )

        student.save()

        return redirect(
            "student_profile",
            student_id=student.id
        )

    return render(
        request,
        "fees/edit_student.html",
        {
            "student": student
        }
    )


# =========================================================
# ADD STUDENT
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def add_student(request):

    if request.method == "POST":

        full_name = request.POST.get(
            "full_name",
            ""
        ).strip()

        name_parts = full_name.split()

        first_name = (
            name_parts[0]
            if name_parts
            else ""
        )

        last_name = (
            " ".join(name_parts[1:])
            if len(name_parts) > 1
            else ""
        )

        Student.objects.create(

            first_name=first_name,

            last_name=last_name,

            student_id=request.POST.get(
                "student_id"
            ),

            registration_number=request.POST.get(
                "registration_number"
            ) or None,

            date_of_birth=request.POST.get(
                "date_of_birth"
            ) or None,

            student_class=request.POST.get(
                "class_name"
            ),

            academic_year=request.POST.get(
                "academic_year"
            ),

            gender=request.POST.get(
                "gender"
            ).title(),

            parent_name=request.POST.get(
                "parent_name"
            ),

            parent_contact=request.POST.get(
                "parent_contact"
            ),

            address=request.POST.get(
                "address"
            ),

            additional_information=request.POST.get(
                "additional_information"
            ),

            photo=request.FILES.get(
                "student_photo"
            ),
        )

        return redirect("students")

    # GET request:
    # Load only active registered classes
    classes = SchoolClass.objects.filter(
        status="Active"
    ).order_by("name")

    return render(
        request,
        "fees/add_student.html",
        {
            "classes": classes
        }
    
)

# =========================================================
# PAYMENTS
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def payments(request):

    payments = Payment.objects.select_related(
        "student"
    ).all().order_by(
        "-payment_date",
        "-id"
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        payments = payments.filter(

            models.Q(
                student__student_id__icontains=search
            )
            |
            models.Q(
                student__first_name__icontains=search
            )
            |
            models.Q(
                student__last_name__icontains=search
            )
            |
            models.Q(
                receipt_number__icontains=search
            )
        )

    # =====================================================
    # CLASS FILTER
    # =====================================================

    student_class = request.GET.get(
        "student_class",
        ""
    ).strip()

    if student_class:

        payments = payments.filter(
            student__student_class=student_class
        )

    # =====================================================
    # DATE FILTER
    # =====================================================

    from_date = request.GET.get(
        "from_date",
        ""
    ).strip()

    to_date = request.GET.get(
        "to_date",
        ""
    ).strip()

    if from_date:

        payments = payments.filter(
            payment_date__gte=from_date
        )

    if to_date:

        payments = payments.filter(
            payment_date__lte=to_date
        )

    # =====================================================
    # TERM FILTER
    # =====================================================

    term = request.GET.get(
        "term",
        ""
    ).strip()

    if term:

        payments = payments.filter(
            term=term
        )

    # =====================================================
    # PAYMENT METHOD FILTER
    # =====================================================

    payment_method = request.GET.get(
        "payment_method",
        ""
    ).strip()

    if payment_method:

        payments = payments.filter(
            payment_method=payment_method
        )

    # =====================================================
    # STATISTICS
    # =====================================================

    total_payments = payments.count()

    total_collected = payments.aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    today = timezone.localdate()

    today_payments = payments.filter(
        payment_date=today
    )

    today_collected = today_payments.aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    # =====================================================
    # FILTER OPTIONS
    # =====================================================

    classes = Student.objects.values_list(
        "student_class",
        flat=True
    ).distinct().order_by(
        "student_class"
    )

    payment_methods = [
        "Cash",
        "Bank Transfer",
        "Mobile Money",
        "Cheque",
        "Card",
    ]

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "fees/payments.html",
        {
            "payments": payments,

            "total_payments": total_payments,

            "total_collected": total_collected,

            "today_payments": today_payments.count(),

            "today_collected": today_collected,

            "classes": classes,

            "payment_methods": payment_methods,

            "search": search,

            "selected_class": student_class,

            "from_date": from_date,

            "to_date": to_date,

            "selected_term": term,

            "selected_payment_method": payment_method,
        }
    )

@login_required
@role_required("school_fees")
def student_profile(request, student_id):

    student = get_object_or_404(
        Student,
        id=student_id
    )

    fee_structure = FeeStructure.objects.filter(
        student_class=student.student_class,
        academic_year=student.academic_year
    ).order_by(
        "-id"
    ).first()

    bill = Bill.objects.filter(
        student=student,
        academic_year=student.academic_year
    ).order_by(
        "-id"
    ).first()

    if bill:

        total_fee = bill.amount_due

    elif fee_structure:

        total_fee = fee_structure.total_fee

    else:

        total_fee = 0

    total_paid = Payment.objects.filter(
        student=student,
        academic_year=student.academic_year
    ).aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    balance = (
        total_fee -
        total_paid
    )

    if balance < 0:

        balance = 0

    payments = Payment.objects.filter(
        student=student,
        academic_year=student.academic_year
    ).order_by(
        "-payment_date",
        "-id"
    )

    discount_percent = (
        bill.discount_percent
        if bill
        else 0
    )

    discount_amount = (
        bill.discount_amount
        if bill
        else 0
    )

    amount_due = (
        bill.amount_due
        if bill
        else total_fee
    )

    context = {

        "student": student,

        "fee_structure": fee_structure,

        "bill": bill,

        "payments": payments,

        "total_fee": total_fee,

        "total_paid": total_paid,

        "balance": balance,

        "discount_percent": discount_percent,

        "discount_amount": discount_amount,

        "amount_due": amount_due,

    }

    return render(
        request,
        "fees/student_profile.html",
        context
    )

# =========================================================
# RECORD PAYMENT
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def record_payment(request):

    if request.method == "POST":

        student_id = request.POST.get(
            "student_id",
            ""
        ).strip()

        student = get_object_or_404(
            Student,
            student_id=student_id
        )

        amount = request.POST.get(
            "amount",
            0
        )

        # -------------------------------------------------
        # AUTO GENERATE RECEIPT NUMBER
        # -------------------------------------------------

        today = timezone.localdate()

        receipt_prefix = (
            f"RCPT-{today.strftime('%Y%m%d')}-"
        )

        last_receipt = Payment.objects.filter(
            receipt_number__startswith=receipt_prefix
        ).order_by(
            "-id"
        ).first()

        if last_receipt and last_receipt.receipt_number:

            try:

                last_number = int(
                    last_receipt.receipt_number.split("-")[-1]
                )

                next_number = last_number + 1

            except (
                ValueError,
                IndexError
            ):

                next_number = 1

        else:

            next_number = 1

        receipt_number = (
            f"{receipt_prefix}"
            f"{next_number:04d}"
        )

        # -------------------------------------------------
        # CREATE PAYMENT
        # -------------------------------------------------

        payment = Payment.objects.create(

            student=student,

            academic_year=student.academic_year,

            term=request.POST.get(
                "term",
                ""
            ),

            amount=amount,

            payment_method=request.POST.get(
                "payment_method",
                ""
            ),

            payment_date=request.POST.get(
                "payment_date"
            ),

            receipt_number=receipt_number,

            description=request.POST.get(
                "description",
                ""
            ).strip(),
        )

        return redirect("print_receipt", payment_id=payment.id)

    registered_classes = (
    Student.objects
    .values_list(
        "student_class",
        flat=True
    )
    .distinct()
    .order_by("student_class")
    )

    return render(
    request,
    "fees/record_payment.html",
    {
        "registered_classes": registered_classes
    }
    )


# =========================================================
# STUDENT PAYMENT LOOKUP
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def student_payment_lookup(request):

    search_type = request.GET.get(
        "search_type",
        "student_id"
    ).strip()

    search_value = request.GET.get(
        "search_value",
        ""
    ).strip()

    term = request.GET.get(
        "term",
        ""
    ).strip()

    # =====================================================
    # CHECK SEARCH VALUE
    # =====================================================

    if not search_value:

        return JsonResponse({
            "success": False,
            "message": "Please enter a search value."
        })

    # =====================================================
    # SEARCH BY STUDENT ID
    # =====================================================

    if search_type == "student_id":

        students = Student.objects.filter(
            student_id__iexact=search_value
        )

    # =====================================================
    # SEARCH BY NAME
    # =====================================================

    elif search_type == "name":

        students = Student.objects.filter(
            models.Q(
                first_name__icontains=search_value
            )
            |
            models.Q(
                last_name__icontains=search_value
            )
        ).order_by(
            "first_name",
            "last_name"
        )

    # =====================================================
    # SEARCH BY CLASS
    # =====================================================

    elif search_type == "class":

        students = Student.objects.filter(
            student_class__iexact=search_value
        ).order_by(
            "first_name",
            "last_name"
        )

    # =====================================================
    # INVALID SEARCH TYPE
    # =====================================================

    else:

        return JsonResponse({
            "success": False,
            "message": "Invalid search type."
        })

    # =====================================================
    # NO STUDENTS FOUND
    # =====================================================

    if not students.exists():

        return JsonResponse({
            "success": False,
            "message": "No student found."
        })

    # =====================================================
    # PREPARE STUDENT RESULTS
    # =====================================================

    results = []

    for student in students:

        results.append({

            "id": student.id,

            "name": (
                f"{student.first_name} "
                f"{student.last_name}"
            ),

            "student_id": student.student_id,

            "class": student.student_class,

            "academic_year": student.academic_year,

        })

    # =====================================================
    # ONE STUDENT FOUND
    # =====================================================

    if len(results) == 1:

        student = students.first()

        # =================================================
        # NO TERM SELECTED
        # =================================================

        if not term:

            return JsonResponse({

                "success": True,

                "multiple": False,

                "student": results[0],

                "fees": {

                    "total_fee": 0,

                    "total_paid": 0,

                    "balance": 0,

                    "discount_percent": 0,

                    "discount_amount": 0,

                    "amount_due": 0,

                }

            })

        # =================================================
        # FIND BILL FOR EXACT TERM
        # =================================================

        bill = Bill.objects.filter(

            student=student,

            academic_year=student.academic_year,

            term=term

        ).order_by(

            "-id"

        ).first()

        # =================================================
        # FIND FEE STRUCTURE FOR EXACT TERM
        # =================================================

        fee_structure = FeeStructure.objects.filter(

            student_class=student.student_class,

            academic_year=student.academic_year,

            term=term

        ).first()

        # =================================================
        # DETERMINE TOTAL FEE
        # =================================================

        if bill:

            total_fee = bill.amount_due

            discount_percent = (
                bill.discount_percent
            )

            discount_amount = (
                bill.discount_amount
            )

        elif fee_structure:

            total_fee = (
                fee_structure.total_fee
            )

            discount_percent = 0

            discount_amount = 0

        else:

            total_fee = 0

            discount_percent = 0

            discount_amount = 0

        # =================================================
        # TOTAL PAID FOR EXACT TERM
        # =================================================

        total_paid = Payment.objects.filter(

            student=student,

            academic_year=student.academic_year,

            term=term

        ).aggregate(

            total=models.Sum("amount")

        )["total"] or 0

        # =================================================
        # CALCULATE BALANCE
        # =================================================

        balance = (
            total_fee -
            total_paid
        )

        if balance < 0:

            balance = 0

        # =================================================
        # RETURN STUDENT + FEE INFORMATION
        # =================================================

        return JsonResponse({

            "success": True,

            "multiple": False,

            "student": results[0],

            "fees": {

                "total_fee": float(
                    total_fee
                ),

                "total_paid": float(
                    total_paid
                ),

                "balance": float(
                    balance
                ),

                "discount_percent": float(
                    discount_percent
                ),

                "discount_amount": float(
                    discount_amount
                ),

                "amount_due": float(
                    total_fee
                ),

            }

        })

    # =====================================================
    # MULTIPLE STUDENTS FOUND
    # =====================================================

    return JsonResponse({

        "success": True,

        "multiple": True,

        "students": results,

    })


# =========================================================
# HOME
# ADMINISTRATOR ONLY
# =========================================================

from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from .models import (
    Student,
    SchoolSettings,
    Payment,
    Bill,
)

# Keep your existing role_required import
# from .decorators import role_required


@login_required
@role_required("administrator")
def home(request):

    # =====================================================
    # CURRENT DATE / ACADEMIC YEAR
    # =====================================================

    today = timezone.localdate()

    school_settings = SchoolSettings.objects.first()

    if school_settings:
        current_academic_year = school_settings.academic_year
    else:
        current_academic_year = f"{today.year}/{today.year + 1}"


    # =====================================================
    # COLLECTION DATE FILTER
    #
    # Default:
    # From Date = Today
    # To Date   = Today
    # =====================================================

    from_date = request.GET.get(
        "from_date",
        ""
    ).strip()

    to_date = request.GET.get(
        "to_date",
        ""
    ).strip()

    if not from_date:
        from_date = today.strftime("%Y-%m-%d")

    if not to_date:
        to_date = today.strftime("%Y-%m-%d")


    # =====================================================
    # TOTAL ACTIVE STUDENTS
    # =====================================================

    total_students = Student.objects.filter(
        status="Active"
    ).count()


    # =====================================================
    # CURRENT ACADEMIC YEAR BILLS
    # =====================================================

    current_bills = Bill.objects.filter(
        academic_year=current_academic_year
    )

    total_fees_due = (
        current_bills.aggregate(
            total=Sum("amount_due")
        )["total"]
        or Decimal("0.00")
    )


    # =====================================================
    # TOTAL SCHOOL FEE PAYMENTS
    # =====================================================

    current_payments = Payment.objects.filter(
        academic_year=current_academic_year
    )

    total_paid = (
        current_payments.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )


    # =====================================================
    # OUTSTANDING
    # =====================================================

    outstanding = total_fees_due - total_paid

    if outstanding < Decimal("0.00"):
        outstanding = Decimal("0.00")


    # =====================================================
    # RECENT PAYMENTS
    # =====================================================

    recent_payments = (
        current_payments
        .select_related("student")
        .order_by(
            "-payment_date",
            "-created_at"
        )[:5]
    )


    # =====================================================
    # STUDENTS BY CLASS
    # =====================================================

    class_counts = (
        Student.objects
        .filter(status="Active")
        .values("student_class")
        .annotate(total=Count("id"))
        .order_by("student_class")
    )

    class_distribution = []

    for item in class_counts:

        count = item["total"]

        percentage = (
            (count / total_students) * 100
            if total_students
            else 0
        )

        class_distribution.append({
            "name": item["student_class"],
            "count": count,
            "percentage": round(
                percentage,
                1
            ),
        })


    # =====================================================
    # STUDENTS BY SCHOOL LEVEL
    # =====================================================

    school_classes = SchoolClass.objects.all()

    level_class_names = defaultdict(set)

    for school_class in school_classes:

        level_class_names[
            school_class.level
        ].add(
            school_class.name
        )

    level_distribution = []

    level_names = [
        "Kindergarten",
        "Primary School",
        "Junior High School",
        "Playgroup",
    ]

    for level in level_names:

        class_names = level_class_names.get(
            level,
            set()
        )

        count = Student.objects.filter(
            status="Active",
            student_class__in=class_names
        ).count()

        percentage = (
            (count / total_students) * 100
            if total_students
            else 0
        )

        level_distribution.append({
            "name": level,
            "count": count,
            "percentage": round(
                percentage,
                1
            ),
        })


    # =====================================================
    # MONTHLY FEE COLLECTION
    # =====================================================

    monthly_bills = (
        current_bills
        .annotate(
            month=TruncMonth("created_at")
        )
        .values("month")
        .annotate(
            total=Sum("amount_due")
        )
        .order_by("month")
    )

    monthly_payments = (
        current_payments
        .annotate(
            month=TruncMonth("payment_date")
        )
        .values("month")
        .annotate(
            total=Sum("amount")
        )
        .order_by("month")
    )

    bills_by_month = {
        item["month"].month: item["total"]
        for item in monthly_bills
    }

    payments_by_month = {
        item["month"].month: item["total"]
        for item in monthly_payments
    }

    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    monthly_chart = []

    cumulative_billed = Decimal("0.00")
    cumulative_paid = Decimal("0.00")

    for month_number in range(1, 13):

        billed = bills_by_month.get(
            month_number,
            Decimal("0.00")
        )

        paid = payments_by_month.get(
            month_number,
            Decimal("0.00")
        )

        cumulative_billed += billed
        cumulative_paid += paid

        month_outstanding = (
            cumulative_billed -
            cumulative_paid
        )

        if month_outstanding < Decimal("0.00"):
            month_outstanding = Decimal("0.00")

        monthly_chart.append({
            "month": month_names[
                month_number - 1
            ],
            "billed": billed,
            "paid": paid,
            "outstanding": month_outstanding,
        })


    # =====================================================
    # COLLECTION UPDATES
    #
    # DATE RANGE
    # =====================================================

    date_filtered_school_payments = (
        Payment.objects
        .filter(
            payment_date__gte=from_date,
            payment_date__lte=to_date
        )
        .select_related("student")
    )


    # =====================================================
    # SCHOOL FEE COLLECTION
    # =====================================================

    school_fee_collected = (
        date_filtered_school_payments.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    school_fee_by_class_query = (
        date_filtered_school_payments
        .values(
            "student__student_class"
        )
        .annotate(
            total=Sum("amount"),
            payments=Count("id")
        )
        .order_by(
            "student__student_class"
        )
    )

    school_fee_by_class = []

    for item in school_fee_by_class_query:

        school_fee_by_class.append({
            "class_name": (
                item["student__student_class"]
                or "Unassigned"
            ),
            "payments": item["payments"],
            "total": item["total"] or Decimal("0.00"),
        })


    # =====================================================
    # FEEDING FEE COLLECTION
    #
    # Paid records and advance payments are counted.
    # =====================================================

    feeding_records = (
        FeedingFeeRecord.objects
        .filter(
            date__gte=from_date,
            date__lte=to_date
        )
        .filter(
            models.Q(status="paid")
            |
            models.Q(status="advance")
            |
            models.Q(is_advance_payment=True)
        )
        .select_related("student")
    )


    feeding_fee_collected = (
        feeding_records.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )


    feeding_fee_by_class_query = (
        feeding_records
        .values(
            "student__student_class"
        )
        .annotate(
            total=Sum("amount"),
            payments=Count("id")
        )
        .order_by(
            "student__student_class"
        )
    )

    feeding_fee_by_class = []

    for item in feeding_fee_by_class_query:

        feeding_fee_by_class.append({
            "class_name": (
                item["student__student_class"]
                or "Unassigned"
            ),
            "payments": item["payments"],
            "total": item["total"] or Decimal("0.00"),
        })


    # =====================================================
    # BUS FEE COLLECTION
    #
    # Paid records and advance payments are counted.
    # =====================================================

    bus_records = (
        BusFeeRecord.objects
        .filter(
            date__gte=from_date,
            date__lte=to_date
        )
        .filter(
            models.Q(status="paid")
            |
            models.Q(is_advance_payment=True)
        )
        .select_related("student")
    )


    bus_fee_collected = (
        bus_records.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )


    bus_fee_by_class_query = (
        bus_records
        .values(
            "student__student_class"
        )
        .annotate(
            total=Sum("amount"),
            payments=Count("id")
        )
        .order_by(
            "student__student_class"
        )
    )

    bus_fee_by_class = []

    for item in bus_fee_by_class_query:

        bus_fee_by_class.append({
            "class_name": (
                item["student__student_class"]
                or "Unassigned"
            ),
            "payments": item["payments"],
            "total": item["total"] or Decimal("0.00"),
        })


    # =====================================================
    # RECENT ACTIVITY
    # =====================================================

    activities = []


    # Recent payments
    recent_payment_activity = (
        current_payments
        .select_related("student")
        .order_by("-created_at")[:5]
    )

    for payment in recent_payment_activity:

        activities.append({
            "type": "payment",
            "icon": "fa-money-bill-wave",
            "title": (
                f"Payment received from "
                f"{payment.student.first_name} "
                f"{payment.student.last_name}"
            ),
            "description": (
                f"GH₵ {payment.amount:,.2f}"
            ),
            "date": payment.created_at,
        })


    # Recently added students
    recent_students = (
        Student.objects
        .filter(status="Active")
        .order_by("-date_registered")[:5]
    )

    for student in recent_students:

        activities.append({
            "type": "student",
            "icon": "fa-user-plus",
            "title": "New student added",
            "description": (
                f"{student.first_name} "
                f"{student.last_name} "
                f"({student.student_class})"
            ),
            "date": student.date_registered,
        })


    # Recently created bills
    recent_bills = (
        current_bills
        .select_related("student")
        .order_by("-created_at")[:5]
    )

    for bill in recent_bills:

        activities.append({
            "type": "bill",
            "icon": "fa-file-invoice",
            "title": (
                f"Bill created for "
                f"{bill.student.first_name} "
                f"{bill.student.last_name}"
            ),
            "description": (
                f"{bill.term} - "
                f"GH₵ {bill.amount_due:,.2f}"
            ),
            "date": bill.created_at,
        })


    activities.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    recent_activity = activities[:5]


    # =====================================================
    # DASHBOARD CONTEXT
    # =====================================================

    context = {

        "current_date": today,

        "current_academic_year":
            current_academic_year,

        "total_students":
            total_students,

        "total_fees_due":
            total_fees_due,

        "total_paid":
            total_paid,

        "outstanding":
            outstanding,

        "recent_payments":
            recent_payments,

        "class_distribution":
            class_distribution,

        "level_distribution":
            level_distribution,

        "monthly_chart":
            monthly_chart,

        "recent_activity":
            recent_activity,


        # =================================================
        # COLLECTION UPDATES
        # =================================================

        "from_date":
            from_date,

        "to_date":
            to_date,

        "school_fee_collected":
            school_fee_collected,

        "feeding_fee_collected":
            feeding_fee_collected,

        "bus_fee_collected":
            bus_fee_collected,

        "school_fee_by_class":
            school_fee_by_class,

        "feeding_fee_by_class":
            feeding_fee_by_class,

        "bus_fee_by_class":
            bus_fee_by_class,
    }


    return render(
        request,
        "fees/home.html",
        context
    )

# =========================================================
# FEES STRUCTURE
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def fees_structure(request):

    fee_structures = FeeStructure.objects.all().order_by(
        "student_class"
    )

    return render(
        request,
        "fees/fees_structure.html",
        {
            "fee_structures": fee_structures
        }
    )


# =========================================================
# ADD FEE STRUCTURE
# SCHOOL FEES
# =========================================================

# =========================================================
# ADD FEE STRUCTURE
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def add_fee_structure(request):

    registered_classes = SchoolClass.objects.filter(
        status="Active"
    ).order_by(
        "level",
        "name"
    )

    if request.method == "POST":

        FeeStructure.objects.create(

            student_class=request.POST.get(
                "student_class",
                ""
            ).strip(),

            academic_year=request.POST.get(
                "academic_year",
                "2026/2027"
            ).strip(),

            term=request.POST.get(
                "term",
                "First Term"
            ).strip(),

            registration_fee=request.POST.get(
                "registration_fee",
                0
            ),

            tuition_fee=request.POST.get(
                "tuition_fee",
                0
            ),

            examination_fee=request.POST.get(
                "examination_fee",
                0
            ),

            library_fee=request.POST.get(
                "library_fee",
                0
            ),

            activity_fee=request.POST.get(
                "activity_fee",
                0
            ),
        )

        return redirect("fees_structure")

    return render(
        request,
        "fees/add_fee_structure.html",
        {
            "registered_classes": registered_classes
        }
    )

# =========================================================
# EDIT FEE STRUCTURE
# SCHOOL FEES
# =========================================================


@login_required
@role_required("school_fees")
def edit_fee_structure(request, fee_id):

    fee_structure = get_object_or_404(
        FeeStructure,
        id=fee_id
    )

    registered_classes = SchoolClass.objects.filter(
        status="Active"
    ).order_by(
        "level",
        "name"
    )

    # Make sure the currently selected class is still available
    # even if it has been changed to Inactive.
    if fee_structure.student_class:
        current_class = SchoolClass.objects.filter(
            name=fee_structure.student_class
        ).first()

        if current_class and current_class not in registered_classes:
            registered_classes = (
                SchoolClass.objects.filter(
                    id=current_class.id
                ) |
                registered_classes
            )

    if request.method == "POST":

        fee_structure.student_class = request.POST.get(
            "student_class",
            ""
        ).strip()

        fee_structure.academic_year = request.POST.get(
            "academic_year",
            "2026/2027"
        ).strip()

        fee_structure.term = request.POST.get(
            "term",
            "First Term"
        ).strip()

        fee_structure.registration_fee = request.POST.get(
            "registration_fee",
            0
        )

        fee_structure.tuition_fee = request.POST.get(
            "tuition_fee",
            0
        )

        fee_structure.examination_fee = request.POST.get(
            "examination_fee",
            0
        )

        fee_structure.library_fee = request.POST.get(
            "library_fee",
            0
        )

        fee_structure.activity_fee = request.POST.get(
            "activity_fee",
            0
        )

        fee_structure.save()

        return redirect("fees_structure")

    return render(
        request,
        "fees/edit_fee_structure.html",
        {
            "fee_structure": fee_structure,
            "registered_classes": registered_classes,
        }
    )

# =========================================================
# DELETE FEE STRUCTURE
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def delete_fee_structure(request, fee_id):

    fee_structure = get_object_or_404(
        FeeStructure,
        id=fee_id
    )

    if request.method == "POST":

        fee_structure.delete()

        return redirect("fees_structure")

    return redirect("fees_structure")

# =========================================================
# REPORTS
# =========================================================

from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from .models import (
    Student,
    SchoolSettings,
    Payment,
    Bill,
    FeeStructure,
)


@login_required
@role_required("administrator")
def reports(request):

    today = timezone.localdate()

    # -----------------------------------------------------
    # CURRENT ACADEMIC YEAR
    # -----------------------------------------------------

    school_settings = SchoolSettings.objects.first()

    if school_settings:
        current_academic_year = school_settings.academic_year
    else:
        current_academic_year = f"{today.year}/{today.year + 1}"


    # -----------------------------------------------------
    # CURRENT MONTH
    # -----------------------------------------------------

    current_month = today.month
    current_year = today.year


    # -----------------------------------------------------
    # STUDENTS
    # -----------------------------------------------------

    total_students = Student.objects.filter(
        status="Active"
    ).count()


    # -----------------------------------------------------
    # BILLS
    # IMPORTANT:
    # Use Bill.amount_due because this includes discounts.
    # -----------------------------------------------------

    current_bills = Bill.objects.filter(
        academic_year=current_academic_year
    )

    total_fees_due = (
        current_bills.aggregate(
            total=Sum("amount_due")
        )["total"]
        or Decimal("0.00")
    )


    # -----------------------------------------------------
    # PAYMENTS
    # -----------------------------------------------------

    current_payments = Payment.objects.filter(
        academic_year=current_academic_year
    )

    total_revenue = (
        current_payments.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    total_payment_count = current_payments.count()


    # -----------------------------------------------------
    # OUTSTANDING
    # -----------------------------------------------------

    outstanding = (
        total_fees_due - total_revenue
    )

    if outstanding < Decimal("0.00"):
        outstanding = Decimal("0.00")


    # -----------------------------------------------------
    # CURRENT MONTH PAYMENTS
    # -----------------------------------------------------

    monthly_payments = current_payments.filter(
        payment_date__year=current_year,
        payment_date__month=current_month
    )

    monthly_revenue = (
        monthly_payments.aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    monthly_payment_count = monthly_payments.count()


    # -----------------------------------------------------
    # CURRENT MONTH BILLS
    # -----------------------------------------------------

    monthly_bills = current_bills.filter(
        created_at__year=current_year,
        created_at__month=current_month
    )

    monthly_billed = (
        monthly_bills.aggregate(
            total=Sum("amount_due")
        )["total"]
        or Decimal("0.00")
    )


    # -----------------------------------------------------
    # PENDING PAYMENT COUNT
    #
    # Count bills that still have money outstanding.
    # -----------------------------------------------------

    pending_payments = 0

    student_bill_data = defaultdict(Decimal)

    for bill in current_bills:

        student_bill_data[bill.student_id] += (
            bill.amount_due
        )

    student_payment_data = defaultdict(Decimal)

    for payment in current_payments:

        student_payment_data[payment.student_id] += (
            payment.amount
        )

    for student_id, billed in student_bill_data.items():

        paid = student_payment_data.get(
            student_id,
            Decimal("0.00")
        )

        if billed > paid:
            pending_payments += 1


    # -----------------------------------------------------
    # MONTHLY PAYMENT CHART
    # -----------------------------------------------------

    monthly_payment_data = (
        current_payments
        .annotate(
            month=TruncMonth("payment_date")
        )
        .values("month")
        .annotate(
            total=Sum("amount")
        )
        .order_by("month")
    )


    monthly_bill_data = (
        current_bills
        .annotate(
            month=TruncMonth("created_at")
        )
        .values("month")
        .annotate(
            total=Sum("amount_due")
        )
        .order_by("month")
    )


    payments_by_month = {
        item["month"].month:
            item["total"]
        for item in monthly_payment_data
    }


    bills_by_month = {
        item["month"].month:
            item["total"]
        for item in monthly_bill_data
    }


    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]


    monthly_chart = []

    max_chart_value = Decimal("0.00")


    for month_number in range(1, 13):

        paid = payments_by_month.get(
            month_number,
            Decimal("0.00")
        )

        billed = bills_by_month.get(
            month_number,
            Decimal("0.00")
        )

        pending = billed - paid

        if pending < Decimal("0.00"):
            pending = Decimal("0.00")


        # Simple overdue representation.
        # Bills that remain unpaid are shown here.
        overdue = Decimal("0.00")


        max_chart_value = max(
            max_chart_value,
            paid,
            pending,
            overdue
        )


        monthly_chart.append({
            "month": month_names[
                month_number - 1
            ],
            "paid": paid,
            "pending": pending,
            "overdue": overdue,
        })


    # Avoid division by zero
    if max_chart_value <= Decimal("0.00"):
        max_chart_value = Decimal("1.00")


    # Calculate chart heights
    for item in monthly_chart:

        item["paid_height"] = float(
            (
                item["paid"] /
                max_chart_value
            ) * 100
        )

        item["pending_height"] = float(
            (
                item["pending"] /
                max_chart_value
            ) * 100
        )

        item["overdue_height"] = float(
            (
                item["overdue"] /
                max_chart_value
            ) * 100
        )


    # -----------------------------------------------------
    # FEE CATEGORY TOTALS
    # -----------------------------------------------------

    fee_structures = FeeStructure.objects.filter(
        academic_year=current_academic_year
    )


    tuition_total = (
        fee_structures.aggregate(
            total=Sum("tuition_fee")
        )["total"]
        or Decimal("0.00")
    )


    examination_total = (
        fee_structures.aggregate(
            total=Sum("examination_fee")
        )["total"]
        or Decimal("0.00")
    )


    library_total = (
        fee_structures.aggregate(
            total=Sum("library_fee")
        )["total"]
        or Decimal("0.00")
    )


    activity_total = (
        fee_structures.aggregate(
            total=Sum("activity_fee")
        )["total"]
        or Decimal("0.00")
    )


    registration_total = (
        fee_structures.aggregate(
            total=Sum("registration_fee")
        )["total"]
        or Decimal("0.00")
    )


    category_total = (
        tuition_total
        + examination_total
        + library_total
        + activity_total
        + registration_total
    )


    fee_categories = []


    categories = [
        (
            "Tuition Fee",
            tuition_total,
            "tuition"
        ),
        (
            "Examination Fee",
            examination_total,
            "examination"
        ),
        (
            "Library Fee",
            library_total,
            "library"
        ),
        (
            "Activity Fee",
            activity_total,
            "activity"
        ),
        (
            "Registration Fee",
            registration_total,
            "other"
        ),
    ]


    for name, amount, css_class in categories:

        percentage = (
            (amount / category_total) * 100
            if category_total > 0
            else Decimal("0.00")
        )

        fee_categories.append({
            "name": name,
            "amount": amount,
            "percentage": round(
                percentage,
                1
            ),
            "css_class": css_class,
        })


    # -----------------------------------------------------
    # CLASS DISTRIBUTION
    # -----------------------------------------------------

    class_counts = (
        Student.objects
        .filter(status="Active")
        .values("student_class")
        .annotate(
            total=Count("id")
        )
        .order_by("-total")
    )


    highest_class = None

    if class_counts:

        highest_class = class_counts[0]


    # -----------------------------------------------------
    # RECENT REPORT ACTIVITY
    #
    # These are based on actual database activity.
    # -----------------------------------------------------

    detailed_reports = []


    # Fee collection report
    if current_payments.exists():

        latest_payment = current_payments.order_by(
            "-created_at"
        ).first()

        detailed_reports.append({
            "name": "Fee Collection Report",
            "description": "Summary of all fee collections",
            "date": latest_payment.created_at,
            "icon": "fa-file-invoice",
            "color": "green",
        })


    # Student payment report
    if current_payments.exists():

        latest_payment = current_payments.order_by(
            "-created_at"
        ).first()

        detailed_reports.append({
            "name": "Student Payment Report",
            "description": "Individual student payment details",
            "date": latest_payment.created_at,
            "icon": "fa-users",
            "color": "blue",
        })


    # Class report
    if class_counts:

        latest_student = Student.objects.filter(
            status="Active"
        ).order_by(
            "-date_registered"
        ).first()

        detailed_reports.append({
            "name": "Class-wise Report",
            "description": "Student distribution by class",
            "date": (
                latest_student.date_registered
                if latest_student
                else today
            ),
            "icon": "fa-graduation-cap",
            "color": "purple",
        })


    # Outstanding report
    if outstanding > 0:

        detailed_reports.append({
            "name": "Outstanding Fees Report",
            "description": "Students with outstanding payments",
            "date": timezone.now(),
            "icon": "fa-triangle-exclamation",
            "color": "red",
        })


    # Monthly summary
    detailed_reports.append({
        "name": "Monthly Summary",
        "description": "Income, billed fees and balance",
        "date": timezone.now(),
        "icon": "fa-chart-column",
        "color": "orange",
    })


    # -----------------------------------------------------
    # QUICK INSIGHTS
    # -----------------------------------------------------

    insights = []


    if monthly_revenue > 0:

        insights.append({
            "color": "green",
            "text": (
                f"GH₵ {monthly_revenue:,.2f} "
                f"has been collected this month."
            ),
        })


    if pending_payments > 0:

        insights.append({
            "color": "orange",
            "text": (
                f"{pending_payments} student"
                f"{'s' if pending_payments != 1 else ''} "
                "still have outstanding payments."
            ),
        })


    if highest_class:

        class_percentage = (
            (
                highest_class["total"] /
                total_students
            ) * 100
            if total_students
            else 0
        )

        insights.append({
            "color": "blue",
            "text": (
                f"{highest_class['student_class']} "
                f"has the highest number of active students "
                f"({highest_class['total']}, "
                f"{class_percentage:.1f}%)."
            ),
        })


    if fee_categories and category_total > 0:

        highest_category = max(
            fee_categories,
            key=lambda item: item["amount"]
        )

        insights.append({
            "color": "purple",
            "text": (
                f"{highest_category['name']} represents "
                f"{highest_category['percentage']}% "
                "of the fee structure."
            ),
        })


    # -----------------------------------------------------
    # NEXT MONTH
    # -----------------------------------------------------

    if current_month == 12:

        next_month_name = "January"
        next_month_year = current_year + 1

    else:

        next_month_name = month_names[
            current_month
        ]

        next_month_year = current_year


    next_report_date = (
        f"01 {next_month_name} "
        f"{next_month_year}"
    )


    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {

        "today": today,

        "current_academic_year":
            current_academic_year,

        "total_revenue":
            total_revenue,

        "total_students":
            total_students,

        "total_payment_count":
            total_payment_count,

        "pending_payments":
            pending_payments,

        "monthly_revenue":
            monthly_revenue,

        "monthly_payment_count":
            monthly_payment_count,

        "monthly_chart":
            monthly_chart,

        "fee_categories":
            fee_categories,

        "category_total":
            category_total,

        "detailed_reports":
            detailed_reports,

        "insights":
            insights,

        "next_report_date":
            next_report_date,
    }


    return render(
        request,
        "fees/reports.html",
        context
    )

# =========================================================
# CLASSES
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def classes(request):

    classes_queryset = SchoolClass.objects.all().order_by("name")

    search = request.GET.get(
        "search",
        ""
    ).strip()

    selected_level = request.GET.get(
        "level",
        ""
    ).strip()

    selected_status = request.GET.get(
        "status",
        ""
    ).strip()

    # SEARCH
    if search:
        classes_queryset = classes_queryset.filter(
            models.Q(name__icontains=search)
            |
            models.Q(level__icontains=search)
        )

    # LEVEL FILTER
    if selected_level:
        classes_queryset = classes_queryset.filter(
            level=selected_level
        )

    # STATUS FILTER
    if selected_status:
        classes_queryset = classes_queryset.filter(
            status=selected_status
        )

    # Number of classes after filters
    total_filtered_classes = classes_queryset.count()

    # Count students belonging to each class
    student_counts = dict(
        Student.objects
        .values("student_class")
        .annotate(
            total=models.Count("id")
        )
        .values_list(
            "student_class",
            "total"
        )
    )

    classes = list(classes_queryset)

    # Attach student count to every class
    for school_class in classes:

        school_class.student_count = student_counts.get(
            school_class.name,
            0
        )

    # Overall statistics
    total_classes = SchoolClass.objects.count()

    total_students = Student.objects.count()

    active_classes = SchoolClass.objects.filter(
        status="Active"
    ).count()

    if total_classes:

        average_students = round(
            total_students / total_classes,
            1
        )

    else:

        average_students = 0

    return render(
        request,
        "fees/classes.html",
        {
            "classes": classes,
            "total_classes": total_classes,
            "total_students": total_students,
            "average_students": average_students,
            "active_classes": active_classes,
            "total_filtered_classes": total_filtered_classes,
            "search": search,
            "selected_level": selected_level,
            "selected_status": selected_status,
        }
    )



# =========================================================
# CREATE BILL
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def create_bill(request):

    if request.method == "POST":

        student_id = request.POST.get("student_id", "").strip()
        academic_year = request.POST.get("academic_year", "").strip()
        term = request.POST.get("term", "").strip()
        discount_percent = request.POST.get(
            "discount_percent",
            "0"
        ).strip()

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not student_id:
            return JsonResponse({
                "success": False,
                "message": "Student not selected."
            })

        if not academic_year:
            return JsonResponse({
                "success": False,
                "message": "Academic year not selected."
            })

        if not term:
            return JsonResponse({
                "success": False,
                "message": "Term not selected."
            })

        # -------------------------------------------------
        # STUDENT
        # -------------------------------------------------

        try:
            student = Student.objects.get(
                id=student_id
            )

        except (
            Student.DoesNotExist,
            ValueError,
            TypeError
        ):

            return JsonResponse({
                "success": False,
                "message": "Student not found."
            })

        # -------------------------------------------------
        # FEE STRUCTURE
        # -------------------------------------------------

        try:

            fee_structure = FeeStructure.objects.get(
                student_class=student.student_class,
                academic_year=academic_year,
                term=term
            )

        except FeeStructure.DoesNotExist:

            return JsonResponse({
                "success": False,
                "message": (
                    "No fee structure has been created for "
                    f"{student.student_class}, "
                    f"{academic_year}, "
                    f"{term}."
                )
            })

        # -------------------------------------------------
        # ORIGINAL TOTAL
        # -------------------------------------------------

        original_total = Decimal(
            str(fee_structure.total_fee or "0")
        )

        # -------------------------------------------------
        # DISCOUNT
        # -------------------------------------------------

        try:

            discount_percent = Decimal(
                str(discount_percent or "0")
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError
        ):

            discount_percent = Decimal("0.00")

        # Keep discount between 0 and 100
        if discount_percent < Decimal("0"):
            discount_percent = Decimal("0")

        if discount_percent > Decimal("100"):
            discount_percent = Decimal("100")

        # -------------------------------------------------
        # CALCULATE DISCOUNT AMOUNT
        # -------------------------------------------------

        discount_amount = (
            original_total *
            discount_percent /
            Decimal("100")
        )

        discount_amount = discount_amount.quantize(
            Decimal("0.01")
        )

        # -------------------------------------------------
        # FINAL AMOUNT DUE
        # -------------------------------------------------

        amount_due = (
            original_total -
            discount_amount
        )

        if amount_due < Decimal("0"):
            amount_due = Decimal("0")

        amount_due = amount_due.quantize(
            Decimal("0.01")
        )

        # -------------------------------------------------
        # CREATE BILL
        # -------------------------------------------------

        bill = Bill.objects.create(

            student=student,

            academic_year=academic_year,

            term=term,

            base_amount=original_total,

            discount_percent=discount_percent,

            discount_amount=discount_amount,

            amount_due=amount_due,

        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return JsonResponse({

            "success": True,

            "message":
                "Bill created successfully.",

            "bill_id":
                bill.id,

            "base_amount":
                str(bill.base_amount),

            "discount_percent":
                str(bill.discount_percent),

            "discount_amount":
                str(bill.discount_amount),

            "amount_due":
                str(bill.amount_due),

        })

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    return render(
        request,
        "fees/create_bill.html"
    )




# =========================================================
# BILL FEE LOOKUP
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def bill_fee_lookup(request):

    student_id = request.GET.get(
        "student_id"
    )

    academic_year = request.GET.get(
        "academic_year"
    )

    term = request.GET.get(
        "term"
    )

    if not student_id:

        return JsonResponse({
            "success": False,
            "message": "Student not selected."
        })

    if not academic_year:

        return JsonResponse({
            "success": False,
            "message": "Academic year not selected."
        })

    if not term:

        return JsonResponse({
            "success": False,
            "message": "Term not selected."
        })

    try:

        student = Student.objects.get(
            id=student_id
        )

    except Student.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": "Student not found."
        })

    try:

        fee_structure = FeeStructure.objects.get(
            student_class=student.student_class,
            academic_year=academic_year,
            term=term
        )

    except FeeStructure.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": (
                "No fee structure has been created for "
                f"{student.student_class}, "
                f"{academic_year}, "
                f"{term}."
            )
        })

    # =====================================================
    # ORIGINAL TERM FEE
    # =====================================================

    original_total = fee_structure.total_fee

    # =====================================================
    # CURRENT STUDENT DISCOUNT
    # =====================================================

    discount_percent = student.discount or 0

    # =====================================================
    # CALCULATE DISCOUNT
    # =====================================================

    discount_amount = (
        original_total *
        discount_percent /
        100
    )

    # =====================================================
    # FINAL AMOUNT REQUIRED
    # =====================================================

    amount_due = (
        original_total -
        discount_amount
    )

    # =====================================================
    # PAYMENTS FOR THIS STUDENT / YEAR / TERM
    # =====================================================

    total_paid = Payment.objects.filter(
        student=student,
        academic_year=academic_year,
        term=term
    ).aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    # =====================================================
    # AMOUNT STILL OWED
    # =====================================================

    amount_owed = (
        amount_due -
        total_paid
    )

    if amount_owed < 0:

        amount_owed = 0

    return JsonResponse({

        "success": True,

        "student": {

            "id": student.id,

            "name": (
                f"{student.first_name} "
                f"{student.last_name}"
            ),

            "student_id": student.student_id,

            "class": student.student_class,

        },

        "fees": {

            "registration_fee": str(
                fee_structure.registration_fee
            ),

            "tuition_fee": str(
                fee_structure.tuition_fee
            ),

            "examination_fee": str(
                fee_structure.examination_fee
            ),

            "library_fee": str(
                fee_structure.library_fee
            ),

            "activity_fee": str(
                fee_structure.activity_fee
            ),

            "original_total": str(
                original_total
            ),

            "discount_percent": str(
                discount_percent
            ),

            "discount_amount": str(
                discount_amount
            ),

            "amount_due": str(
                amount_due
            ),

            "total_paid": str(
                total_paid
            ),

            "amount_owed": str(
                amount_owed
            ),

        }

    })


# =========================================================
# BUS FEES
# BUS FEE USER
# =========================================================

@login_required
@role_required("bus_fee")
def bus_fees(request):

    selected_class = request.GET.get(
        "student_class",
        ""
    ).strip()

    selected_date = request.GET.get(
        "date",
        ""
    ).strip()

    # =====================================================
    # SELECTED DATE
    # =====================================================

    if selected_date:

        try:

            current_date = date.fromisoformat(
                selected_date
            )

        except ValueError:

            current_date = date.today()

    else:

        current_date = date.today()

    # =====================================================
    # CALCULATE WEEK
    # =====================================================

    monday = current_date - timedelta(
        days=current_date.weekday()
    )

    week_dates = [
        monday + timedelta(days=i)
        for i in range(5)
    ]

    friday = week_dates[-1]

    previous_week = monday - timedelta(
        days=7
    )

    next_week = monday + timedelta(
        days=7
    )

    # =====================================================
    # ALL CLASSES
    # =====================================================

    classes = (
        Student.objects
        .filter(status="Active")
        .values_list(
            "student_class",
            flat=True
        )
        .distinct()
        .order_by(
            "student_class"
        )
    )

    # =====================================================
    # SCHOOL-WIDE BUS FEE
    # =====================================================

    bus_structure = (
        BusFeeStructure.objects
        .order_by("-updated_at")
        .first()
    )

    if bus_structure:

        daily_fee = bus_structure.daily_fee

    else:

        daily_fee = Decimal("0.00")

    # =====================================================
    # WEEKLY FEE
    # =====================================================

    weekly_class_fee = daily_fee * 5

    students = []

    # =====================================================
    # GET STUDENTS FOR SELECTED CLASS
    # =====================================================

    if selected_class:

        students_queryset = (
            Student.objects
            .filter(
                student_class=selected_class,
                status="Active"
            )
            .order_by(
                "first_name",
                "last_name"
            )
        )

        # =================================================
        # GET BUS RECORDS
        # =================================================

        records = (
            BusFeeRecord.objects
            .filter(
                student__in=students_queryset,
                date__in=week_dates
            )
        )

        # =================================================
        # ORGANIZE RECORDS
        # =================================================

        record_lookup = {}

        for record in records:

            key = (
                record.student_id,
                record.date
            )

            record_lookup[key] = record

        # =================================================
        # BUILD STUDENT ROWS
        # =================================================

        for student in students_queryset:

            student_days = []

            weekly_paid = Decimal("0.00")

            days_paid = 0

            for day in week_dates:

                record = record_lookup.get(
                    (
                        student.id,
                        day
                    )
                )

                if record:

                    status = record.status

                    amount = record.amount

                    if (
                        amount == 0
                        and daily_fee
                    ):

                        amount = daily_fee

                else:

                    status = "unmarked"

                    amount = Decimal("0.00")

                # =========================================
                # COUNT PAID / ADVANCE
                # =========================================

                if status in [
                    "paid",
                    "advance"
                ]:

                    weekly_paid += amount

                    days_paid += 1

                student_days.append({

                    "date": day,

                    "record": record,

                    "status": status,

                    "amount": amount,

                })

            # =================================================
            # AMOUNT DUE
            # =================================================

            weekly_due = daily_fee * 5

            amount_due = (
                weekly_due -
                weekly_paid
            )

            if amount_due < 0:

                amount_due = Decimal("0.00")

            students.append({

                "student": student,

                "days": student_days,

                "weekly_paid": weekly_paid,

                "weekly_due": weekly_due,

                "amount_due": amount_due,

                "days_paid": days_paid,

            })

    # =====================================================
    # PAGE CONTEXT
    # =====================================================

    context = {

        "selected_class":
            selected_class,

        "classes":
            classes,

        "students":
            students,

        "week_dates":
            week_dates,

        "monday":
            monday,

        "friday":
            friday,

        "previous_week":
            previous_week,

        "next_week":
            next_week,

        "daily_fee":
            daily_fee,

        "weekly_class_fee":
            weekly_class_fee,

    }

    return render(
        request,
        "fees/bus_fees.html",
        context
    )


# =========================================================
# BUS / FEEDING FEE STRUCTURE
#
# Bus users can ONLY use type=bus.
# Feeding users can ONLY use type=feeding.
# Administrator can use either.
# =========================================================

@login_required
@role_required(
    "bus_fee",
    "feeding_fee"
)
def bus_fee_structure(request):

    # =====================================================
    # DETERMINE USER ROLE
    # =====================================================

    if request.user.is_superuser:

        user_role = "administrator"

    else:

        try:

            user_role = request.user.profile.role

        except UserProfile.DoesNotExist:

            logout(request)

            return redirect("login")

    # =====================================================
    # SELECT FEE TYPE
    # =====================================================

    requested_type = request.GET.get(
        "type",
        "bus"
    ).strip().lower()

    # -----------------------------------------------------
    # FORCE ROLE TO CORRECT FEE TYPE
    # -----------------------------------------------------

    if user_role == "bus_fee":

        fee_type = "bus"

    elif user_role == "feeding_fee":

        fee_type = "feeding"

    else:

        fee_type = requested_type

        if fee_type not in [
            "bus",
            "feeding"
        ]:

            fee_type = "bus"

    # =====================================================
    # SAVE DAILY FEE
    # =====================================================

    if request.method == "POST":

        requested_post_type = request.POST.get(
            "fee_type",
            "bus"
        ).strip().lower()

        # -------------------------------------------------
        # FORCE ROLE RESTRICTION
        # -------------------------------------------------

        if user_role == "bus_fee":

            fee_type = "bus"

        elif user_role == "feeding_fee":

            fee_type = "feeding"

        else:

            fee_type = requested_post_type

            if fee_type not in [
                "bus",
                "feeding"
            ]:

                fee_type = "bus"

        daily_fee_value = request.POST.get(
            "daily_fee",
            ""
        ).strip()

        try:

            daily_fee = Decimal(
                daily_fee_value
            )

            if daily_fee < 0:

                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            daily_fee = Decimal("0.00")

        # =================================================
        # BUS FEE
        # =================================================

        if fee_type == "bus":

            fee_structure = (
                BusFeeStructure.objects
                .order_by("-updated_at")
                .first()
            )

            if fee_structure:

                fee_structure.daily_fee = daily_fee

                fee_structure.save()

            else:

                BusFeeStructure.objects.create(
                    daily_fee=daily_fee
                )

        # =================================================
        # FEEDING FEE
        # =================================================

        else:

            fee_structure = (
                FeedingFeeStructure.objects
                .order_by("-updated_at")
                .first()
            )

            if fee_structure:

                fee_structure.daily_fee = daily_fee

                fee_structure.save()

            else:

                FeedingFeeStructure.objects.create(
                    daily_fee=daily_fee
                )

        return redirect(
            f"/bus-fee-structure/?type={fee_type}"
        )

    # =====================================================
    # WEEK CALCULATION
    # =====================================================

    selected_date = request.GET.get(
        "date",
        ""
    ).strip()

    if selected_date:

        try:

            current_date = date.fromisoformat(
                selected_date
            )

        except ValueError:

            current_date = date.today()

    else:

        current_date = date.today()

    monday = current_date - timedelta(
        days=current_date.weekday()
    )

    friday = monday + timedelta(
        days=4
    )

    previous_week = monday - timedelta(
        days=7
    )

    next_week = monday + timedelta(
        days=7
    )

    week_dates = [
        monday + timedelta(days=i)
        for i in range(5)
    ]

    # =====================================================
    # GET CORRECT FEE STRUCTURE
    # =====================================================

    if fee_type == "bus":

        fee_structure = (
            BusFeeStructure.objects
            .order_by("-updated_at")
            .first()
        )

    else:

        fee_structure = (
            FeedingFeeStructure.objects
            .order_by("-updated_at")
            .first()
        )

    if fee_structure:

        daily_fee = fee_structure.daily_fee

    else:

        daily_fee = Decimal("0.00")

    weekly_fee = daily_fee * 5

    # =====================================================
    # ACTIVE STUDENTS / CLASSES
    # =====================================================

    classes = (
        Student.objects
        .filter(
            status="Active"
        )
        .values_list(
            "student_class",
            flat=True
        )
        .distinct()
        .order_by(
            "student_class"
        )
    )

    # =====================================================
    # GET CORRECT RECORDS
    # =====================================================

    if fee_type == "bus":

        fee_records = (
            BusFeeRecord.objects
            .filter(
                date__in=week_dates
            )
            .select_related(
                "student"
            )
        )

    else:

        fee_records = (
            FeedingFeeRecord.objects
            .filter(
                date__in=week_dates
            )
            .select_related(
                "student"
            )
        )

    # =====================================================
    # WEEKLY CLASS SUMMARY
    # =====================================================

    class_summaries = []

    total_students = 0

    total_paid = 0

    total_absent = 0

    total_unpaid = 0

    total_advance_days = 0

    total_collection = Decimal("0.00")

    for student_class in classes:

        students = (
            Student.objects
            .filter(
                student_class=student_class,
                status="Active"
            )
        )

        student_ids = set(
            students.values_list(
                "id",
                flat=True
            )
        )

        class_records = [
            record
            for record in fee_records
            if record.student_id in student_ids
        ]

        # =================================================
        # PAID
        # =================================================

        present = sum(
            1
            for record in class_records
            if record.status == "paid"
        )

        # =================================================
        # ABSENT
        # =================================================

        absent = sum(
            1
            for record in class_records
            if record.status == "absent"
        )

        # =================================================
        # PRESENT BUT NOT PAID
        # =================================================

        not_paid = sum(
            1
            for record in class_records
            if record.status == "present_not_paid"
        )

        # =================================================
        # ADVANCE
        # =================================================

        advance_days = sum(
            1
            for record in class_records
            if record.is_advance_payment
        )

        # =================================================
        # COLLECTION
        # =================================================

        collection = sum(
            (
                record.amount
                for record in class_records
                if (
                    record.status == "paid"
                    or record.is_advance_payment
                )
            ),
            Decimal("0.00")
        )

        student_count = len(
            student_ids
        )

        class_summaries.append({

            "student_class":
                student_class,

            "total_students":
                student_count,

            "present":
                present,

            "absent":
                absent,

            "not_paid":
                not_paid,

            "advance_days":
                advance_days,

            "collection":
                collection,

        })

        total_students += student_count

        total_paid += present

        total_absent += absent

        total_unpaid += not_paid

        total_advance_days += advance_days

        total_collection += collection

    # =====================================================
    # PAGE LABELS
    # =====================================================

    if fee_type == "bus":

        fee_name = "Bus Fee"

        fee_icon = "🚌"

        fee_description = (
            "Bus fee settings and weekly collection summary"
        )

        settings_description = (
            "Set the daily bus fee for all students."
        )

        daily_label = "Daily Bus Fee"

        save_label = "Save Bus Fee"

        collector_url = "bus_fees"

    else:

        fee_name = "Feeding Fee"

        fee_icon = "🍽️"

        fee_description = (
            "Feeding fee settings and weekly collection summary"
        )

        settings_description = (
            "Set the daily feeding fee for all students."
        )

        daily_label = "Daily Feeding Fee"

        save_label = "Save Feeding Fee"

        collector_url = "feeding_fees"

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "fee_type":
            fee_type,

        "fee_name":
            fee_name,

        "fee_icon":
            fee_icon,

        "fee_description":
            fee_description,

        "settings_description":
            settings_description,

        "daily_label":
            daily_label,

        "save_label":
            save_label,

        "collector_url":
            collector_url,

        "class_summaries":
            class_summaries,

        "monday":
            monday,

        "friday":
            friday,

        "previous_week":
            previous_week,

        "next_week":
            next_week,

        "week_dates":
            week_dates,

        "daily_fee":
            daily_fee,

        "weekly_fee":
            weekly_fee,

        "total_students":
            total_students,

        "total_paid":
            total_paid,

        "total_absent":
            total_absent,

        "total_unpaid":
            total_unpaid,

        "total_advance_days":
            total_advance_days,

        "total_collection":
            total_collection,

    }

    return render(
        request,
        "fees/bus_fee_structure.html",
        context
    )


# =========================================================
# SAVE BUS STATUS
# BUS FEE USER
# =========================================================

@login_required
@role_required("bus_fee")
@require_POST
def save_bus_status(request):

    student_id = request.POST.get(
        "student_id"
    )

    selected_date = request.POST.get(
        "date"
    )

    status = request.POST.get(
        "status"
    )

    allowed_statuses = [
        "paid",
        "absent",
        "present_not_paid",
        "advance",
        "clear",
    ]

    if status not in allowed_statuses:

        return JsonResponse({
            "success": False,
            "message": "Invalid status."
        }, status=400)

    try:

        student = Student.objects.get(
            id=student_id
        )

        record_date = date.fromisoformat(
            selected_date
        )

    except (
        Student.DoesNotExist,
        ValueError
    ):

        return JsonResponse({
            "success": False,
            "message": "Invalid student or date."
        }, status=400)

    # =====================================================
    # CLEAR
    # =====================================================

    if status == "clear":

        BusFeeRecord.objects.filter(
            student=student,
            date=record_date
        ).delete()

        return JsonResponse({
            "success": True,
            "status": "clear"
        })

    # =====================================================
    # GET GLOBAL BUS FEE
    # =====================================================

    bus_structure = (
        BusFeeStructure.objects
        .order_by("-updated_at")
        .first()
    )

    if bus_structure:

        daily_fee = bus_structure.daily_fee

    else:

        daily_fee = Decimal("0.00")

    # =====================================================
    # CREATE / FIND DAILY RECORD
    # =====================================================

    record, created = (
        BusFeeRecord.objects.get_or_create(
            student=student,
            date=record_date
        )
    )

    record.status = status

    # =====================================================
    # ADVANCE PAYMENT
    # =====================================================

    if status == "advance":

        record.is_advance_payment = True

    else:

        record.is_advance_payment = False

    # =====================================================
    # SAVE CURRENT DAILY FEE
    # =====================================================

    record.amount = daily_fee

    record.save()

    return JsonResponse({

        "success": True,

        "status": status,

        "amount": str(
            record.amount
        )

    })


# =========================================================
# FEEDING FEES
# FEEDING FEE USER
# =========================================================

@login_required
@role_required("feeding_fee")
def feeding_fees(request):

    selected_class = request.GET.get(
        "student_class",
        ""
    ).strip()

    selected_date = request.GET.get(
        "date",
        ""
    ).strip()

    # =====================================================
    # SELECTED DATE
    # =====================================================

    if selected_date:

        try:

            current_date = date.fromisoformat(
                selected_date
            )

        except ValueError:

            current_date = date.today()

    else:

        current_date = date.today()

    # =====================================================
    # WEEK
    # =====================================================

    monday = current_date - timedelta(
        days=current_date.weekday()
    )

    week_dates = [
        monday + timedelta(days=i)
        for i in range(5)
    ]

    friday = week_dates[-1]

    previous_week = monday - timedelta(
        days=7
    )

    next_week = monday + timedelta(
        days=7
    )

    # =====================================================
    # CLASSES
    # =====================================================

    classes = (
        Student.objects
        .filter(
            status="Active"
        )
        .values_list(
            "student_class",
            flat=True
        )
        .distinct()
        .order_by(
            "student_class"
        )
    )

    # =====================================================
    # SCHOOL-WIDE FEEDING FEE
    # =====================================================

    feeding_structure = (
        FeedingFeeStructure.objects
        .order_by("-updated_at")
        .first()
    )

    if feeding_structure:

        daily_fee = feeding_structure.daily_fee

    else:

        daily_fee = Decimal("0.00")

    # =====================================================
    # WEEKLY FEE
    # =====================================================

    weekly_class_fee = daily_fee * 5

    students = []

    # =====================================================
    # GET STUDENTS FOR SELECTED CLASS
    # =====================================================

    if selected_class:

        students_queryset = (
            Student.objects
            .filter(
                student_class=selected_class,
                status="Active"
            )
            .order_by(
                "first_name",
                "last_name"
            )
        )

        # =================================================
        # GET FEEDING RECORDS
        # =================================================

        records = (
            FeedingFeeRecord.objects
            .filter(
                student__in=students_queryset,
                date__in=week_dates
            )
        )

        # =================================================
        # ORGANIZE RECORDS
        # =================================================

        record_lookup = {}

        for record in records:

            key = (
                record.student_id,
                record.date
            )

            record_lookup[key] = record

        # =================================================
        # BUILD STUDENT ROWS
        # =================================================

        for student in students_queryset:

            student_days = []

            weekly_paid = Decimal("0.00")

            days_paid = 0

            for day in week_dates:

                record = record_lookup.get(
                    (
                        student.id,
                        day
                    )
                )

                if record:

                    status = record.status

                    amount = record.amount

                    if (
                        amount == 0
                        and daily_fee
                    ):

                        amount = daily_fee

                else:

                    status = "unmarked"

                    amount = Decimal("0.00")

                # =========================================
                # COUNT PAID / ADVANCE
                # =========================================

                if status in [
                    "paid",
                    "advance"
                ]:

                    weekly_paid += amount

                    days_paid += 1

                student_days.append({

                    "date": day,

                    "record": record,

                    "status": status,

                    "amount": amount,

                })

            # =================================================
            # AMOUNT DUE
            # =================================================

            weekly_due = daily_fee * 5

            amount_due = (
                weekly_due -
                weekly_paid
            )

            if amount_due < 0:

                amount_due = Decimal("0.00")

            students.append({

                "student": student,

                "days": student_days,

                "weekly_paid": weekly_paid,

                "weekly_due": weekly_due,

                "amount_due": amount_due,

                "days_paid": days_paid,

            })

    # =====================================================
    # PAGE CONTEXT
    # =====================================================

    context = {

        "selected_class":
            selected_class,

        "classes":
            classes,

        "students":
            students,

        "week_dates":
            week_dates,

        "monday":
            monday,

        "friday":
            friday,

        "previous_week":
            previous_week,

        "next_week":
            next_week,

        "daily_fee":
            daily_fee,

        "weekly_class_fee":
            weekly_class_fee,

    }

    # =====================================================
    # RETURN PAGE
    # =====================================================

    return render(
        request,
        "fees/feeding_fees.html",
        context
    )

@login_required
@role_required("school_fees")
def add_class(request):

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        level = request.POST.get(
            "level",
            ""
        ).strip()

        class_teacher = request.POST.get(
            "class_teacher",
            ""
        ).strip()

        status = request.POST.get(
            "status",
            "Active"
        ).strip()

        if not name:

            messages.error(
                request,
                "Please enter a class name."
            )

            return render(
                request,
                "fees/add_class.html"
            )

        if not level:

            messages.error(
                request,
                "Please select a class level."
            )

            return render(
                request,
                "fees/add_class.html"
            )

        if SchoolClass.objects.filter(
            name__iexact=name
        ).exists():

            messages.error(
                request,
                "A class with this name already exists."
            )

            return render(
                request,
                "fees/add_class.html"
            )

        SchoolClass.objects.create(
            name=name,
            level=level,
            class_teacher=class_teacher,
            status=status
        )

        messages.success(
            request,
            f"{name} was added successfully."
        )

        return redirect("classes")

    return render(
        request,
        "fees/add_class.html"
    )


@login_required
@role_required("school_fees")
def view_class(request, class_id):

    school_class = get_object_or_404(
        SchoolClass,
        id=class_id
    )

    students = Student.objects.filter(
        student_class=school_class.name
    ).order_by(
        "first_name",
        "last_name"
    )

    return render(
        request,
        "fees/view_class.html",
        {
            "school_class": school_class,
            "students": students,
            "student_count": students.count(),
        }
    )


@login_required
@role_required("school_fees")
def edit_class(request, class_id):

    school_class = get_object_or_404(
        SchoolClass,
        id=class_id
    )

    old_name = school_class.name

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        level = request.POST.get(
            "level",
            ""
        ).strip()

        class_teacher = request.POST.get(
            "class_teacher",
            ""
        ).strip()

        status = request.POST.get(
            "status",
            "Active"
        ).strip()

        if not name:

            messages.error(
                request,
                "Please enter a class name."
            )

            return render(
                request,
                "fees/edit_class.html",
                {
                    "school_class": school_class
                }
            )

        if not level:

            messages.error(
                request,
                "Please select a class level."
            )

            return render(
                request,
                "fees/edit_class.html",
                {
                    "school_class": school_class
                }
            )

        duplicate = SchoolClass.objects.filter(
            name__iexact=name
        ).exclude(
            id=school_class.id
        ).exists()

        if duplicate:

            messages.error(
                request,
                "Another class with this name already exists."
            )

            return render(
                request,
                "fees/edit_class.html",
                {
                    "school_class": school_class
                }
            )

        school_class.name = name
        school_class.level = level
        school_class.class_teacher = class_teacher
        school_class.status = status

        school_class.save()

        # Keep existing students connected if
        # the class name was changed.
        if old_name != name:

            Student.objects.filter(
                student_class=old_name
            ).update(
                student_class=name
            )

        messages.success(
            request,
            f"{name} was updated successfully."
        )

        return redirect(
            "classes"
        )

    return render(
        request,
        "fees/edit_class.html",
        {
            "school_class": school_class
        }
    )


    return redirect(
        "classes"
    )

    # =====================================================
    # FEEDING FEE STRUCTURE
    # =====================================================

    feeding_structure = (
        FeedingFeeStructure.objects
        .order_by("-updated_at")
        .first()
    )

    if feeding_structure:

        daily_fee = (
            feeding_structure.daily_fee
        )

    else:

        daily_fee = Decimal("0.00")

    weekly_class_fee = (
        daily_fee * 5
    )

    students = []

    # =====================================================
    # STUDENTS
    # =====================================================

    if selected_class:

        students_queryset = (
            Student.objects
            .filter(
                student_class=selected_class,
                status="Active"
            )
            .order_by(
                "first_name",
                "last_name"
            )
        )

        records = (
            FeedingFeeRecord.objects
            .filter(
                student__in=students_queryset,
                date__in=week_dates
            )
        )

        record_lookup = {}

        for record in records:

            key = (
                record.student_id,
                record.date
            )

            record_lookup[key] = record

        # =================================================
        # BUILD STUDENT DATA
        # =================================================

        for student in students_queryset:

            student_days = []

            weekly_paid = Decimal("0.00")

            days_paid = 0

            for day in week_dates:

                record = record_lookup.get(
                    (
                        student.id,
                        day
                    )
                )

                if record:

                    status = record.status

                    amount = record.amount

                    if (
                        amount == 0
                        and daily_fee
                    ):

                        amount = daily_fee

                else:

                    status = "unmarked"

                    amount = Decimal("0.00")

                # =========================================
                # PAID / ADVANCE
                # =========================================

                if status in [
                    "paid",
                    "advance"
                ]:

                    weekly_paid += amount

                    days_paid += 1

                student_days.append({

                    "date": day,

                    "record": record,

                    "status": status,

                    "amount": amount,

                })

            # =================================================
            # WEEKLY AMOUNT
            # =================================================

            weekly_due = (
                daily_fee * 5
            )

            amount_due = (
                weekly_due -
                weekly_paid
            )

            if amount_due < 0:

                amount_due = Decimal("0.00")

            students.append({

                "student": student,

                "days": student_days,

                "weekly_paid": weekly_paid,

                "weekly_due": weekly_due,

                "amount_due": amount_due,

                "days_paid": days_paid,

            })

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "selected_class":
            selected_class,

        "classes":
            classes,

        "students":
            students,

        "week_dates":
            week_dates,

        "monday":
            monday,

        "friday":
            friday,

        "previous_week":
            previous_week,

        "next_week":
            next_week,

        "daily_fee":
            daily_fee,

        "weekly_class_fee":
            weekly_class_fee,

    }

    return render(
        request,
        "fees/feeding_fees.html",
        context
    )


# =========================================================
# SAVE FEEDING STATUS
# FEEDING FEE USER
# =========================================================

@login_required
@role_required("feeding_fee")
@require_POST
def save_feeding_status(request):

    student_id = request.POST.get(
        "student_id"
    )

    selected_date = request.POST.get(
        "date"
    )

    status = request.POST.get(
        "status"
    )

    allowed_statuses = [
        "paid",
        "absent",
        "present_not_paid",
        "advance",
        "clear",
    ]

    if status not in allowed_statuses:

        return JsonResponse({
            "success": False,
            "message": "Invalid status."
        }, status=400)

    try:

        student = Student.objects.get(
            id=student_id
        )

        record_date = date.fromisoformat(
            selected_date
        )

    except (
        Student.DoesNotExist,
        ValueError
    ):

        return JsonResponse({
            "success": False,
            "message": "Invalid student or date."
        }, status=400)

    # =====================================================
    # CLEAR STATUS
    # =====================================================

    if status == "clear":

        FeedingFeeRecord.objects.filter(
            student=student,
            date=record_date
        ).delete()

        return JsonResponse({
            "success": True,
            "status": "clear"
        })

    # =====================================================
    # GET CURRENT FEEDING FEE
    # =====================================================

    feeding_structure = (
        FeedingFeeStructure.objects
        .order_by("-updated_at")
        .first()
    )

    if feeding_structure:

        daily_fee = (
            feeding_structure.daily_fee
        )

    else:

        daily_fee = Decimal("0.00")

    # =====================================================
    # CREATE / UPDATE RECORD
    # =====================================================

    record, created = (
        FeedingFeeRecord.objects.get_or_create(
            student=student,
            date=record_date
        )
    )

    record.status = status

    if status == "advance":

        record.is_advance_payment = True

    else:

        record.is_advance_payment = False

    record.amount = daily_fee

    record.save()

    return JsonResponse({

        "success": True,

        "status": status,

        "amount": str(
            record.amount
        )

    })


# =========================================================
# USERS MANAGEMENT
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def users_management(request):

    users = (
        User.objects
        .select_related("profile")
        .exclude(
            id=request.user.id
        )
        .order_by(
            "username"
        )
    )

    return render(
        request,
        "fees/users_management.html",
        {
            "users": users,
        }
    )


# =========================================================
# CREATE USER
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def create_user(request):

    if request.method == "POST":

        full_name = request.POST.get(
            "full_name",
            ""
        ).strip()

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        role = request.POST.get(
            "role",
            ""
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not full_name:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        "Please enter the user's full name."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        if not username:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        "Please enter a username."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        if not password:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        "Please enter a password."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        if password != confirm_password:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        "Passwords do not match."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        if role not in [
            "school_fees",
            "bus_fee",
            "feeding_fee",
        ]:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        "Please select a valid user role."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        # =================================================
        # CHECK USERNAME
        # =================================================

        if User.objects.filter(
            username=username
        ).exists():

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        f"The username '{username}' "
                        "already exists. Please choose "
                        "another username."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        # =================================================
        # SPLIT FULL NAME
        # =================================================

        name_parts = full_name.split(
            " ",
            1
        )

        first_name = name_parts[0]

        last_name = ""

        if len(name_parts) > 1:

            last_name = name_parts[1]

        # =================================================
        # CREATE USER
        # =================================================

        try:

            user = User.objects.create_user(

                username=username,

                password=password,

                first_name=first_name,

                last_name=last_name

            )

        except IntegrityError:

            return render(
                request,
                "fees/create_user.html",
                {
                    "error": (
                        f"The username '{username}' "
                        "already exists. Please choose "
                        "another username."
                    ),
                    "full_name": full_name,
                    "username": username,
                    "role": role,
                }
            )

        # =================================================
        # CREATE USER PROFILE
        # =================================================

        UserProfile.objects.create(

            user=user,

            role=role

        )

        # =================================================
        # SUCCESS
        # =================================================

        return redirect(
            "users_management"
        )

    # =====================================================
    # GET REQUEST
    # =====================================================

    return render(
        request,
        "fees/create_user.html"
    )


# =========================================================
# EDIT USER
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def edit_user(request, user_id):

    user = get_object_or_404(
        User,
        id=user_id
    )

    # =====================================================
    # ADMINISTRATOR CANNOT EDIT THEMSELVES
    # =====================================================

    if user.id == request.user.id:

        messages.error(
            request,
            (
                "You cannot edit your own "
                "administrator account here."
            )
        )

        return redirect(
            "users_management"
        )

    profile = get_object_or_404(
        UserProfile,
        user=user
    )

    if request.method == "POST":

        full_name = request.POST.get(
            "full_name",
            ""
        ).strip()

        username = request.POST.get(
            "username",
            ""
        ).strip()

        role = request.POST.get(
            "role",
            ""
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not full_name:

            return render(
                request,
                "fees/edit_user.html",
                {
                    "user_account": user,
                    "profile": profile,
                    "error": (
                        "Please enter the user's full name."
                    ),
                }
            )

        if not username:

            return render(
                request,
                "fees/edit_user.html",
                {
                    "user_account": user,
                    "profile": profile,
                    "error": (
                        "Please enter a username."
                    ),
                }
            )

        if role not in [
            "school_fees",
            "bus_fee",
            "feeding_fee",
        ]:

            return render(
                request,
                "fees/edit_user.html",
                {
                    "user_account": user,
                    "profile": profile,
                    "error": (
                        "Please select a valid user role."
                    ),
                }
            )

        # =================================================
        # CHECK USERNAME
        # =================================================

        username_exists = (
            User.objects
            .filter(
                username=username
            )
            .exclude(
                id=user.id
            )
            .exists()
        )

        if username_exists:

            return render(
                request,
                "fees/edit_user.html",
                {
                    "user_account": user,
                    "profile": profile,
                    "error": (
                        f"The username '{username}' "
                        "already exists."
                    ),
                }
            )

        # =================================================
        # SPLIT FULL NAME
        # =================================================

        name_parts = full_name.split(
            " ",
            1
        )

        first_name = name_parts[0]

        last_name = ""

        if len(name_parts) > 1:

            last_name = name_parts[1]

        # =================================================
        # UPDATE USER
        # =================================================

        try:

            user.username = username

            user.first_name = first_name

            user.last_name = last_name

            user.save()

        except IntegrityError:

            return render(
                request,
                "fees/edit_user.html",
                {
                    "user_account": user,
                    "profile": profile,
                    "error": (
                        "That username is already in use."
                    ),
                }
            )

        # =================================================
        # UPDATE PROFILE
        # =================================================

        profile.role = role

        profile.save()

        messages.success(
            request,
            (
                f"User '{username}' was "
                "updated successfully."
            )
        )

        return redirect(
            "users_management"
        )

    # =====================================================
    # GET REQUEST
    # =====================================================

    return render(
        request,
        "fees/edit_user.html",
        {
            "user_account": user,
            "profile": profile,
        }
    )


# =========================================================
# CHANGE USER PASSWORD
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def change_user_password(request, user_id):

    user = get_object_or_404(
        User,
        id=user_id
    )

    # =====================================================
    # ADMINISTRATOR CANNOT CHANGE OWN PASSWORD HERE
    # =====================================================

    if user.id == request.user.id:

        messages.error(
            request,
            (
                "You cannot change your own "
                "administrator password here."
            )
        )

        return redirect(
            "users_management"
        )

    if request.method == "POST":

        password = request.POST.get(
            "password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not password:

            return render(
                request,
                "fees/change_user_password.html",
                {
                    "user_account": user,
                    "error": (
                        "Please enter a new password."
                    ),
                }
            )

        if password != confirm_password:

            return render(
                request,
                "fees/change_user_password.html",
                {
                    "user_account": user,
                    "error": (
                        "Passwords do not match."
                    ),
                }
            )

        if len(password) < 8:

            return render(
                request,
                "fees/change_user_password.html",
                {
                    "user_account": user,
                    "error": (
                        "Password must contain at least "
                        "8 characters."
                    ),
                }
            )

        # =================================================
        # CHANGE PASSWORD
        # =================================================

        user.set_password(
            password
        )

        user.save()

        messages.success(
            request,
            (
                f"Password for '{user.username}' "
                "was changed successfully."
            )
        )

        return redirect(
            "users_management"
        )

    # =====================================================
    # GET REQUEST
    # =====================================================

    return render(
        request,
        "fees/change_user_password.html",
        {
            "user_account": user,
        }
    )


# =========================================================
# DELETE USER
# ADMINISTRATOR ONLY
# =========================================================

@login_required
@role_required("administrator")
def delete_user(request, user_id):

    user = get_object_or_404(
        User,
        id=user_id
    )

    # =====================================================
    # NEVER ALLOW ADMIN TO DELETE THEMSELVES
    # =====================================================

    if user.id == request.user.id:

        messages.error(
            request,
            (
                "You cannot delete your own "
                "administrator account."
            )
        )

        return redirect(
            "users_management"
        )

    if request.method == "POST":

        username = user.username

        user.delete()

        messages.success(
            request,
            (
                f"User '{username}' "
                "was deleted successfully."
            )
        )

        return redirect(
            "users_management"
        )

    return render(
        request,
        "fees/delete_user.html",
        {
            "user_account": user,
        }
    )

# =========================================================
# PRINT PAYMENT RECEIPT
# SCHOOL FEES
# =========================================================

@login_required
def print_receipt(request, payment_id):

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related("student"),
        id=payment_id
    )

    student = payment.student


    # -----------------------------------------------------
    # SCHOOL SETTINGS
    # -----------------------------------------------------

    settings = SchoolSettings.objects.first()


    # -----------------------------------------------------
    # GET STUDENT FEE STRUCTURE
    # SAME LOGIC AS STUDENT PAYMENT LOOKUP
    # -----------------------------------------------------

    fee_structure = FeeStructure.objects.filter(
        student_class=student.student_class,
        academic_year=student.academic_year
    ).first()


    if fee_structure:

        total_fee = fee_structure.total_fee

    else:

        total_fee = 0


    # -----------------------------------------------------
    # GET ALL PAYMENTS BEFORE THIS PAYMENT
    # -----------------------------------------------------

    previous_payments = Payment.objects.filter(
        student=student,
        academic_year=student.academic_year
    ).filter(

        models.Q(
            payment_date__lt=payment.payment_date
        )

        |

        models.Q(
            payment_date=payment.payment_date,
            id__lt=payment.id
        )

    )


    # -----------------------------------------------------
    # TOTAL PAID BEFORE THIS PAYMENT
    # -----------------------------------------------------

    total_previous_paid = (
        previous_payments.aggregate(
            total=models.Sum("amount")
        )["total"] or 0
    )


    # -----------------------------------------------------
    # ARREARS BEFORE CURRENT PAYMENT
    # -----------------------------------------------------

    arrears_before_payment = (
        total_fee - total_previous_paid
    )


    if arrears_before_payment < 0:

        arrears_before_payment = 0


    # -----------------------------------------------------
    # BALANCE AFTER CURRENT PAYMENT
    # -----------------------------------------------------

    balance_after_payment = (
        arrears_before_payment - payment.amount
    )


    if balance_after_payment < 0:

        balance_after_payment = 0


    # -----------------------------------------------------
    # TOTAL PAID INCLUDING CURRENT PAYMENT
    # -----------------------------------------------------

    total_paid = (
        total_previous_paid + payment.amount
    )


    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {

        "payment": payment,

        "student": student,

        "settings": settings,

        "fee_structure": fee_structure,

        "total_fee": total_fee,

        "total_previous_paid": total_previous_paid,

        "total_paid": total_paid,

        "arrears_before_payment": (
            arrears_before_payment
        ),

        "balance_after_payment": (
            balance_after_payment
        ),

    }


    return render(
        request,
        "fees/print_receipt.html",
        context
    )

# =========================================================
# EXPORT ALL DATA TO EXCEL
# ADMINISTRATOR
# =========================================================

@login_required
def export_excel(request):

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from django.utils import timezone
    from decimal import Decimal

    # =====================================================
    # HELPER - EXCEL DATETIME
    # =====================================================

    def excel_datetime(value):

        if value is None:
            return None

        if timezone.is_aware(value):
            return timezone.make_naive(value)

        return value

    # =====================================================
    # CREATE WORKBOOK
    # =====================================================

    workbook = Workbook()

    # Remove default sheet
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    # =====================================================
    # COMMON SHEET FORMATTING
    # =====================================================

    def format_sheet(sheet):

        # Header
        for cell in sheet[1]:

            cell.font = Font(
                bold=True
            )

            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="D9EAF7"
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center"
            )

        # Freeze header
        sheet.freeze_panes = "A2"

        # Auto width
        for column_cells in sheet.columns:

            max_length = 0

            column_letter = get_column_letter(
                column_cells[0].column
            )

            for cell in column_cells:

                try:

                    cell_length = len(
                        str(cell.value)
                    )

                    if cell_length > max_length:
                        max_length = cell_length

                except Exception:
                    pass

            sheet.column_dimensions[
                column_letter
            ].width = min(
                max_length + 2,
                40
            )

    # =====================================================
    # 1. STUDENTS
    # =====================================================

    sheet = workbook.create_sheet(
        "Students"
    )

    sheet.append([
        "ID",
        "First Name",
        "Last Name",
        "Student ID",
        "Registration Number",
        "Date of Birth",
        "Class",
        "Academic Year",
        "Gender",
        "Parent Name",
        "Parent Contact",
        "Address",
        "Additional Information",
        "Status",
        "Fee Status",
        "Discount",
        "Total Fee",
        "Total Paid",
        "Balance",
        "Photo",
        "Date Registered",
    ])

    students = Student.objects.all().order_by(
        "id"
    )

    for student in students:

        # =================================================
        # EXACT SAME FEE CALCULATION AS PAYMENT SYSTEM
        # =================================================

        fee_structure = FeeStructure.objects.filter(

            student_class=student.student_class,

            academic_year=student.academic_year

        ).first()

        # -------------------------------------------------
        # TOTAL FEE
        # -------------------------------------------------

        if fee_structure:

            total_fee = (
                fee_structure.total_fee
            )

        else:

            total_fee = Decimal("0.00")

        # -------------------------------------------------
        # TOTAL PAID
        # -------------------------------------------------

        total_paid = Payment.objects.filter(

            student=student,

            academic_year=student.academic_year

        ).aggregate(

            total=models.Sum("amount")

        )["total"] or Decimal("0.00")

        # -------------------------------------------------
        # BALANCE
        # -------------------------------------------------

        balance = (
            total_fee -
            total_paid
        )

        # -------------------------------------------------
        # FEE STATUS
        # EXACT SAME LOGIC AS WEBSITE
        # -------------------------------------------------

        if total_fee <= 0:

            calculated_fee_status = "Pending"

        elif total_paid >= total_fee:

            calculated_fee_status = "Paid"

        else:

            calculated_fee_status = "Pending"

        # =================================================
        # ADD STUDENT ROW
        # =================================================

        sheet.append([

            student.id,

            student.first_name,

            student.last_name,

            student.student_id,

            student.registration_number,

            student.date_of_birth,

            student.student_class,

            student.academic_year,

            student.gender,

            student.parent_name,

            student.parent_contact,

            student.address,

            student.additional_information,

            student.status,

            calculated_fee_status,

            float(
                student.discount or 0
            ),

            float(
                total_fee
            ),

            float(
                total_paid
            ),

            float(
                balance
            ),

            (
                str(student.photo.url)
                if student.photo
                else ""
            ),

            excel_datetime(
                student.date_registered
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 2. CLASSES
    # =====================================================

    sheet = workbook.create_sheet(
        "Classes"
    )

    sheet.append([
        "ID",
        "Class Name",
        "Level",
        "Class Teacher",
        "Status",
        "Created At",
        "Updated At",
    ])

    for school_class in SchoolClass.objects.all().order_by("id"):

        sheet.append([

            school_class.id,

            school_class.name,

            school_class.level,

            school_class.class_teacher,

            school_class.status,

            excel_datetime(
                school_class.created_at
            ),

            excel_datetime(
                school_class.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 3. SCHOOL SETTINGS
    # =====================================================

    sheet = workbook.create_sheet(
        "School Settings"
    )

    sheet.append([
        "ID",
        "School Name",
        "Address",
        "Phone",
        "Email",
        "Academic Year",
        "School Motto",
        "Logo",
    ])

    for settings in SchoolSettings.objects.all().order_by("id"):

        sheet.append([

            settings.id,

            settings.school_name,

            settings.address,

            settings.phone,

            settings.email,

            settings.academic_year,

            settings.school_motto,

            (
                str(settings.logo.url)
                if settings.logo
                else ""
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 4. FEE STRUCTURES
    # =====================================================

    sheet = workbook.create_sheet(
        "Fee Structures"
    )

    sheet.append([
        "ID",
        "Class",
        "Academic Year",
        "Term",
        "Registration Fee",
        "Tuition Fee",
        "Examination Fee",
        "Library Fee",
        "Activity Fee",
        "Total Fee",
        "Created At",
        "Updated At",
    ])

    for fee in FeeStructure.objects.all().order_by("id"):

        sheet.append([

            fee.id,

            fee.student_class,

            fee.academic_year,

            fee.term,

            float(
                fee.registration_fee or 0
            ),

            float(
                fee.tuition_fee or 0
            ),

            float(
                fee.examination_fee or 0
            ),

            float(
                fee.library_fee or 0
            ),

            float(
                fee.activity_fee or 0
            ),

            float(
                fee.total_fee
            ),

            excel_datetime(
                fee.created_at
            ),

            excel_datetime(
                fee.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 5. PAYMENTS
    # =====================================================

    sheet = workbook.create_sheet(
        "Payments"
    )

    sheet.append([
        "ID",
        "Student ID",
        "Student Name",
        "Academic Year",
        "Term",
        "Amount",
        "Payment Method",
        "Payment Date",
        "Receipt Number",
        "Description",
        "Created At",
    ])

    payments = Payment.objects.select_related(
        "student"
    ).all().order_by("id")

    for payment in payments:

        sheet.append([

            payment.id,

            payment.student.student_id,

            (
                f"{payment.student.first_name} "
                f"{payment.student.last_name}"
            ),

            payment.academic_year,

            payment.term,

            float(
                payment.amount or 0
            ),

            payment.payment_method,

            payment.payment_date,

            payment.receipt_number,

            payment.description,

            excel_datetime(
                payment.created_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 6. BILLS
    # =====================================================

    sheet = workbook.create_sheet(
        "Bills"
    )

    sheet.append([
        "ID",
        "Student ID",
        "Student Name",
        "Academic Year",
        "Term",
        "Base Amount",
        "Discount Percent",
        "Discount Amount",
        "Amount Due",
        "Created At",
    ])

    bills = Bill.objects.select_related(
        "student"
    ).all().order_by("id")

    for bill in bills:

        sheet.append([

            bill.id,

            bill.student.student_id,

            (
                f"{bill.student.first_name} "
                f"{bill.student.last_name}"
            ),

            bill.academic_year,

            bill.term,

            float(
                bill.base_amount or 0
            ),

            float(
                bill.discount_percent or 0
            ),

            float(
                bill.discount_amount or 0
            ),

            float(
                bill.amount_due or 0
            ),

            excel_datetime(
                bill.created_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 7. BUS FEE STRUCTURES
    # =====================================================

    sheet = workbook.create_sheet(
        "Bus Fee Structures"
    )

    sheet.append([
        "ID",
        "Daily Fee",
        "Academic Year",
        "Created At",
        "Updated At",
    ])

    for fee in BusFeeStructure.objects.all().order_by("id"):

        sheet.append([

            fee.id,

            float(
                fee.daily_fee or 0
            ),

            fee.academic_year,

            excel_datetime(
                fee.created_at
            ),

            excel_datetime(
                fee.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 8. BUS FEE RECORDS
    # =====================================================

    sheet = workbook.create_sheet(
        "Bus Fee Records"
    )

    sheet.append([
        "ID",
        "Student ID",
        "Student Name",
        "Date",
        "Status",
        "Amount",
        "Advance Payment",
        "Created At",
        "Updated At",
    ])

    bus_records = BusFeeRecord.objects.select_related(
        "student"
    ).all().order_by("id")

    for record in bus_records:

        sheet.append([

            record.id,

            record.student.student_id,

            (
                f"{record.student.first_name} "
                f"{record.student.last_name}"
            ),

            record.date,

            record.status,

            float(
                record.amount or 0
            ),

            record.is_advance_payment,

            excel_datetime(
                record.created_at
            ),

            excel_datetime(
                record.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 9. FEEDING FEE STRUCTURES
    # =====================================================

    sheet = workbook.create_sheet(
        "Feeding Fee Structures"
    )

    sheet.append([
        "ID",
        "Daily Fee",
        "Academic Year",
        "Created At",
        "Updated At",
    ])

    for fee in FeedingFeeStructure.objects.all().order_by("id"):

        sheet.append([

            fee.id,

            float(
                fee.daily_fee or 0
            ),

            fee.academic_year,

            excel_datetime(
                fee.created_at
            ),

            excel_datetime(
                fee.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # 10. FEEDING FEE RECORDS
    # =====================================================

    sheet = workbook.create_sheet(
        "Feeding Fee Records"
    )

    sheet.append([
        "ID",
        "Student ID",
        "Student Name",
        "Date",
        "Status",
        "Amount",
        "Advance Payment",
        "Created At",
        "Updated At",
    ])

    feeding_records = FeedingFeeRecord.objects.select_related(
        "student"
    ).all().order_by("id")

    for record in feeding_records:

        sheet.append([

            record.id,

            record.student.student_id,

            (
                f"{record.student.first_name} "
                f"{record.student.last_name}"
            ),

            record.date,

            record.status,

            float(
                record.amount or 0
            ),

            record.is_advance_payment,

            excel_datetime(
                record.created_at
            ),

            excel_datetime(
                record.updated_at
            ),

        ])

    format_sheet(sheet)

    # =====================================================
    # RESPONSE
    # =====================================================

    response = HttpResponse(

        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )

    )

    response["Content-Disposition"] = (
        'attachment; '
        'filename="Smart_System_Export.xlsx"'
    )

    workbook.save(
        response
    )

    return response

# =========================================================
# IMPORT / RESTORE FROM EXCEL
# =========================================================

@login_required
@role_required("administrator")
def import_excel(request):

    if request.method != "POST":
        return redirect("settings")

    from openpyxl import load_workbook
    from django.db import transaction
    from django.contrib import messages
    from datetime import datetime, date
    from decimal import Decimal

    uploaded_file = request.FILES.get("excel_file")

    # =====================================================
    # CHECK FILE
    # =====================================================

    if not uploaded_file:

        messages.error(
            request,
            "Please select an Excel backup file."
        )

        return redirect("settings")

    if not uploaded_file.name.lower().endswith(".xlsx"):

        messages.error(
            request,
            "Only .xlsx Excel files are supported."
        )

        return redirect("settings")

    try:

        workbook = load_workbook(
            uploaded_file,
            data_only=True
        )

        # =================================================
        # REQUIRED SHEETS
        # =================================================

        required_sheets = [
            "Students",
            "Classes",
            "School Settings",
            "Fee Structures",
            "Payments",
            "Bills",
            "Bus Fee Structures",
            "Bus Fee Records",
            "Feeding Fee Structures",
            "Feeding Fee Records",
        ]

        missing_sheets = [
            sheet
            for sheet in required_sheets
            if sheet not in workbook.sheetnames
        ]

        if missing_sheets:

            messages.error(
                request,
                "Invalid Smart System backup. Missing sheets: "
                + ", ".join(missing_sheets)
            )

            return redirect("settings")

        # =================================================
        # HELPERS
        # =================================================

        def clean(value):

            if value is None:
                return None

            if isinstance(value, str):

                value = value.strip()

                if value == "":
                    return None

            return value

        def decimal_value(value):

            value = clean(value)

            if value is None:
                return Decimal("0.00")

            try:
                return Decimal(str(value))
            except Exception:
                return Decimal("0.00")

        def date_value(value):

            value = clean(value)

            if value is None:
                return None

            if isinstance(value, datetime):
                return value.date()

            if isinstance(value, date):
                return value

            return value

        def datetime_value(value):

            value = clean(value)

            if value is None:
                return None

            if isinstance(value, datetime):
                return value

            if isinstance(value, date):

                return datetime.combine(
                    value,
                    datetime.min.time()
                )

            return value

        def boolean_value(value):

            value = clean(value)

            if isinstance(value, bool):
                return value

            if value is None:
                return False

            value = str(value).strip().lower()

            return value in [
                "true",
                "1",
                "yes",
                "y",
                "on",
            ]

        def rows(sheet_name):

            sheet = workbook[sheet_name]

            headers = [
                clean(cell.value)
                for cell in sheet[1]
            ]

            for row in sheet.iter_rows(
                min_row=2,
                values_only=True
            ):

                if not any(
                    clean(value) is not None
                    for value in row
                ):
                    continue

                yield dict(
                    zip(
                        headers,
                        row
                    )
                )

        # =================================================
        # IMPORT EVERYTHING
        # =================================================

        with transaction.atomic():

            # =================================================
            # 1. CLASSES
            # =================================================

            for row in rows("Classes"):

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "name": clean(
                        row.get("Class Name")
                    ) or "",

                    "level": clean(
                        row.get("Level")
                    ) or "",

                    "class_teacher": clean(
                        row.get("Class Teacher")
                    ),

                    "status": clean(
                        row.get("Status")
                    ) or "Active",
                }

                if record_id:

                    SchoolClass.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    SchoolClass.objects.get_or_create(
                        name=defaults["name"],
                        defaults=defaults
                    )

            # =================================================
            # 2. SCHOOL SETTINGS
            # =================================================

            for row in rows("School Settings"):

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "school_name": clean(
                        row.get("School Name")
                    ) or "School Name",

                    "address": clean(
                        row.get("Address")
                    ),

                    "phone": clean(
                        row.get("Phone")
                    ),

                    "email": clean(
                        row.get("Email")
                    ),

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "2026/2027",

                    "school_motto": clean(
                        row.get("School Motto")
                    ),
                }

                if record_id:

                    SchoolSettings.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    SchoolSettings.objects.update_or_create(
                        id=1,
                        defaults=defaults
                    )

            # =================================================
            # 3. STUDENTS
            # =================================================

            for row in rows("Students"):

                record_id = clean(
                    row.get("ID")
                )

                student_id = clean(
                    row.get("Student ID")
                )

                if not student_id:
                    continue

                defaults = {

                    "first_name": clean(
                        row.get("First Name")
                    ) or "",

                    "last_name": clean(
                        row.get("Last Name")
                    ) or "",

                    "student_id": student_id,

                    "registration_number": clean(
                        row.get("Registration Number")
                    ),

                    "date_of_birth": date_value(
                        row.get("Date of Birth")
                    ),

                    "student_class": clean(
                        row.get("Class")
                    ) or "",

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "2026/2027",

                    "gender": clean(
                        row.get("Gender")
                    ) or "",

                    "parent_name": clean(
                        row.get("Parent Name")
                    ),

                    "parent_contact": clean(
                        row.get("Parent Contact")
                    ),

                    "address": clean(
                        row.get("Address")
                    ),

                    "additional_information": clean(
                        row.get("Additional Information")
                    ),

                    "status": clean(
                        row.get("Status")
                    ) or "Active",

                    "fee_status": clean(
                        row.get("Fee Status")
                    ) or "Pending",

                    "discount": decimal_value(
                        row.get("Discount")
                    ),

                    "balance": decimal_value(
                        row.get("Balance")
                    ),
                }

                # ---------------------------------------------
                # IMPORTANT:
                # Existing students are primarily matched
                # using Student ID.
                # ---------------------------------------------

                existing_student = None

                if record_id:

                    existing_student = Student.objects.filter(
                        id=record_id
                    ).first()

                if not existing_student:

                    existing_student = Student.objects.filter(
                        student_id=student_id
                    ).first()

                if existing_student:

                    for field, value in defaults.items():

                        setattr(
                            existing_student,
                            field,
                            value
                        )

                    existing_student.save()

                else:

                    Student.objects.create(
                        **defaults
                    )

            # =================================================
            # 4. FEE STRUCTURES
            # =================================================

            for row in rows("Fee Structures"):

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "student_class": clean(
                        row.get("Class")
                    ) or "",

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "2026/2027",

                    "term": clean(
                        row.get("Term")
                    ) or "First Term",

                    "registration_fee": decimal_value(
                        row.get("Registration Fee")
                    ),

                    "tuition_fee": decimal_value(
                        row.get("Tuition Fee")
                    ),

                    "examination_fee": decimal_value(
                        row.get("Examination Fee")
                    ),

                    "library_fee": decimal_value(
                        row.get("Library Fee")
                    ),

                    "activity_fee": decimal_value(
                        row.get("Activity Fee")
                    ),
                }

                if record_id:

                    FeeStructure.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    FeeStructure.objects.update_or_create(
                        student_class=defaults["student_class"],
                        academic_year=defaults["academic_year"],
                        term=defaults["term"],
                        defaults=defaults
                    )

            # =================================================
            # 5. PAYMENTS
            # =================================================

            for row in rows("Payments"):

                student_id = clean(
                    row.get("Student ID")
                )

                if not student_id:
                    continue

                # ---------------------------------------------
                # CORRECT:
                # Excel contains Student.student_id
                # ---------------------------------------------

                student = Student.objects.filter(
                    student_id=student_id
                ).first()

                if not student:
                    continue

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "student": student,

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "",

                    "term": clean(
                        row.get("Term")
                    ) or "First Term",

                    "amount": decimal_value(
                        row.get("Amount")
                    ),

                    "payment_method": clean(
                        row.get("Payment Method")
                    ) or "",

                    "payment_date": date_value(
                        row.get("Payment Date")
                    ),

                    "receipt_number": clean(
                        row.get("Receipt Number")
                    ),

                    "description": clean(
                        row.get("Description")
                    ),
                }

                if record_id:

                    Payment.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    Payment.objects.create(
                        **defaults
                    )

            # =================================================
            # 6. BILLS
            # =================================================

            for row in rows("Bills"):

                student_id = clean(
                    row.get("Student ID")
                )

                if not student_id:
                    continue

                student = Student.objects.filter(
                    student_id=student_id
                ).first()

                if not student:
                    continue

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "student": student,

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "",

                    "term": clean(
                        row.get("Term")
                    ) or "First Term",

                    "base_amount": decimal_value(
                        row.get("Base Amount")
                    ),

                    "discount_percent": decimal_value(
                        row.get("Discount Percent")
                    ),

                    "discount_amount": decimal_value(
                        row.get("Discount Amount")
                    ),

                    "amount_due": decimal_value(
                        row.get("Amount Due")
                    ),
                }

                if record_id:

                    Bill.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    Bill.objects.create(
                        **defaults
                    )

            # =================================================
            # 7. BUS FEE STRUCTURES
            # =================================================

            for row in rows("Bus Fee Structures"):

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "daily_fee": decimal_value(
                        row.get("Daily Fee")
                    ),

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "2026/2027",
                }

                if record_id:

                    BusFeeStructure.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    BusFeeStructure.objects.update_or_create(
                        academic_year=defaults["academic_year"],
                        defaults=defaults
                    )

            # =================================================
            # 8. BUS FEE RECORDS
            # =================================================

            for row in rows("Bus Fee Records"):

                student_id = clean(
                    row.get("Student ID")
                )

                if not student_id:
                    continue

                student = Student.objects.filter(
                    student_id=student_id
                ).first()

                if not student:
                    continue

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "student": student,

                    "date": date_value(
                        row.get("Date")
                    ),

                    "status": clean(
                        row.get("Status")
                    ) or "unmarked",

                    "amount": decimal_value(
                        row.get("Amount")
                    ),

                    "is_advance_payment": boolean_value(
                        row.get("Advance Payment")
                    ),
                }

                if record_id:

                    BusFeeRecord.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    BusFeeRecord.objects.update_or_create(
                        student=student,
                        date=defaults["date"],
                        defaults=defaults
                    )

            # =================================================
            # 9. FEEDING FEE STRUCTURES
            # =================================================

            for row in rows("Feeding Fee Structures"):

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "daily_fee": decimal_value(
                        row.get("Daily Fee")
                    ),

                    "academic_year": clean(
                        row.get("Academic Year")
                    ) or "2026/2027",
                }

                if record_id:

                    FeedingFeeStructure.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    FeedingFeeStructure.objects.update_or_create(
                        academic_year=defaults["academic_year"],
                        defaults=defaults
                    )

            # =================================================
            # 10. FEEDING FEE RECORDS
            # =================================================

            for row in rows("Feeding Fee Records"):

                student_id = clean(
                    row.get("Student ID")
                )

                if not student_id:
                    continue

                student = Student.objects.filter(
                    student_id=student_id
                ).first()

                if not student:
                    continue

                record_id = clean(
                    row.get("ID")
                )

                defaults = {

                    "student": student,

                    "date": date_value(
                        row.get("Date")
                    ),

                    "status": clean(
                        row.get("Status")
                    ) or "unmarked",

                    "amount": decimal_value(
                        row.get("Amount")
                    ),

                    "is_advance_payment": boolean_value(
                        row.get("Advance Payment")
                    ),
                }

                if record_id:

                    FeedingFeeRecord.objects.update_or_create(
                        id=record_id,
                        defaults=defaults
                    )

                else:

                    FeedingFeeRecord.objects.update_or_create(
                        student=student,
                        date=defaults["date"],
                        defaults=defaults
                    )

        # =====================================================
        # SUCCESS
        # =====================================================

        messages.success(
            request,
            "Excel backup restored successfully. "
            "Students, fees, payments, bills, bus and feeding "
            "records have been imported."
        )

    except Exception as e:

        messages.error(
            request,
            f"Import failed: {str(e)}"
        )

    return redirect("settings")

