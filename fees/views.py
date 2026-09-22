
from functools import wraps
from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, models
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Student,
    SchoolSettings,
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

        if request.FILES.get("school_logo"):

            settings.logo = request.FILES.get(
                "school_logo"
            )

        settings.save()

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

        student.fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()

        # -------------------------------------------------
        # TOTAL FEE
        # -------------------------------------------------

        if student.fee_structure:

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
# STUDENT PROFILE
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def student_profile(request, student_id):

    student = get_object_or_404(
        Student,
        id=student_id
    )

    # =====================================================
    # FEE STRUCTURE
    # =====================================================

    fee_structure = FeeStructure.objects.filter(
        student_class=student.student_class,
        academic_year=student.academic_year
    ).first()

    # =====================================================
    # TOTAL FEE
    # =====================================================

    if fee_structure:

        total_fee = fee_structure.total_fee

    else:

        total_fee = 0

    # =====================================================
    # PAYMENT HISTORY
    # =====================================================

    payments = Payment.objects.filter(
        student=student,
        academic_year=student.academic_year
    ).order_by(
        "-payment_date",
        "-id"
    )

    # =====================================================
    # TOTAL PAID
    # =====================================================

    total_paid = payments.aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    # =====================================================
    # BALANCE
    # =====================================================

    balance = total_fee - total_paid

    # =====================================================
    # FEE STATUS
    # =====================================================

    if total_fee <= 0:

        fee_status = "Pending"

    elif total_paid >= total_fee:

        fee_status = "Paid"

    else:

        fee_status = "Pending"

    # =====================================================
    # PAYMENT COUNT
    # =====================================================

    payment_count = payments.count()

    # =====================================================
    # RETURN PROFILE
    # =====================================================

    return render(
        request,
        "fees/student_profile.html",
        {
            "student": student,
            "fee_structure": fee_structure,
            "payments": payments,
            "total_fee": total_fee,
            "total_paid": total_paid,
            "balance": balance,
            "fee_status": fee_status,
            "payment_count": payment_count,
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

        student.stream = request.POST.get(
            "stream",
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

            stream=request.POST.get(
                "stream"
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

    return render(
        request,
        "fees/add_student.html"
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
    # ACADEMIC YEAR FILTER
    # =====================================================

    academic_year = request.GET.get(
        "academic_year",
        ""
    ).strip()

    if academic_year:

        payments = payments.filter(
            academic_year=academic_year
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

    academic_years = Payment.objects.values_list(
        "academic_year",
        flat=True
    ).distinct().order_by(
        "-academic_year"
    )

    payment_methods = [
        "Cash",
        "Bank Transfer",
        "Mobile Money",
        "Cheque",
        "Card",
    ]

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
            "academic_years": academic_years,
            "payment_methods": payment_methods,
            "search": search,
            "selected_class": student_class,
            "selected_academic_year": academic_year,
            "selected_term": term,
            "selected_payment_method": payment_method,
        }
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

        Payment.objects.create(

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

        return redirect("payments")

    return render(
        request,
        "fees/record_payment.html"
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
    # PREPARE RESULTS
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
    # ONLY ONE STUDENT
    # =====================================================

    if len(results) == 1:

        student = students.first()

        fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()

        total_fee = (
            fee_structure.total_fee
            if fee_structure
            else 0
        )

        total_paid = Payment.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        balance = total_fee - total_paid

        return JsonResponse({

            "success": True,

            "multiple": False,

            "student": results[0],

            "fees": {

                "total_fee": float(total_fee),

                "total_paid": float(total_paid),

                "balance": float(balance),

            }

        })

    # =====================================================
    # MULTIPLE STUDENTS
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

@login_required
@role_required("administrator")
def home(request):

    return render(
        request,
        "fees/home.html"
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

@login_required
@role_required("school_fees")
def add_fee_structure(request):

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
        "fees/add_fee_structure.html"
    )


# =========================================================
# REPORTS
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def reports(request):

    return render(
        request,
        "fees/reports.html"
    )


# =========================================================
# CLASSES
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def classes(request):

    return render(
        request,
        "fees/classes.html"
    )


# =========================================================
# CREATE BILL
# SCHOOL FEES
# =========================================================

@login_required
@role_required("school_fees")
def create_bill(request):

    if request.method == "POST":

        student_id = request.POST.get(
            "student_id"
        )

        academic_year = request.POST.get(
            "academic_year"
        )

        term = request.POST.get(
            "term"
        )

        discount_percent = request.POST.get(
            "discount_percent",
            0
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

        original_total = fee_structure.total_fee

        try:

            discount_percent = float(
                discount_percent
            )

        except (
            TypeError,
            ValueError
        ):

            discount_percent = 0

        if discount_percent < 0:

            discount_percent = 0

        if discount_percent > 100:

            discount_percent = 100

        discount_amount = (
            original_total *
            discount_percent /
            100
        )

        amount_due = (
            original_total -
            discount_amount
        )

        bill = Bill.objects.create(

            student=student,

            academic_year=academic_year,

            term=term,

            base_amount=original_total,

            discount_percent=discount_percent,

            discount_amount=discount_amount,

            amount_due=amount_due,
        )

        return JsonResponse({

            "success": True,

            "message": "Bill created successfully.",

            "bill_id": bill.id,

        })

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

