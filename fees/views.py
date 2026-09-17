from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.http import JsonResponse
from django.db import models
from django.utils import timezone

from .models import Student, SchoolSettings, FeeStructure, Payment


def logout_view(request):
    logout(request)
    return redirect("home")


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
            settings.logo = request.FILES.get("school_logo")

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
# =========================================================

def students(request):

    students = Student.objects.all().order_by("-date_registered")

    # Attach the matching fee structure to every student
    for student in students:

        student.fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()

    return render(
        request,
        "fees/students.html",
        {
            "students": students,
            "total_students": students.count(),
            "active_students": students.filter(
                status="Active"
            ).count(),
            "inactive_students": students.filter(
                status="Inactive"
            ).count(),
            "new_admissions": students.filter(
                academic_year="2026/2027"
            ).count(),
        }
    )

# =========================================================
# STUDENT PROFILE
# =========================================================

def student_profile(request, student_id):

    student = get_object_or_404(
        Student,
        id=student_id
    )

    # Find the fee structure for this student's
    # class and academic year.
    fee_structure = FeeStructure.objects.filter(
        student_class=student.student_class,
        academic_year=student.academic_year
    ).first()

    return render(
        request,
        "fees/student_profile.html",
        {
            "student": student,
            "fee_structure": fee_structure
        }
    )


# =========================================================
# EDIT STUDENT
# =========================================================

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

        # Only replace the photo if a new photo was selected.
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
# =========================================================

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
# =========================================================

def payments(request):
    return render(
        request,
        "fees/payments.html"
    )


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

            except (ValueError, IndexError):

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


    # ==========================================
    # SEARCH BY STUDENT ID
    # ==========================================

    if search_type == "student_id":

        students = Student.objects.filter(
            student_id__iexact=search_value
        )


    # ==========================================
    # SEARCH BY NAME
    # ==========================================

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


    # ==========================================
    # SEARCH BY CLASS
    # ==========================================

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


    # ==========================================
    # NO STUDENTS FOUND
    # ==========================================

    if not students.exists():

        return JsonResponse({
            "success": False,
            "message": "No student found."
        })


    # ==========================================
    # PREPARE RESULTS
    # ==========================================

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


    # ==========================================
    # ONLY ONE STUDENT
    # ==========================================

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


    # ==========================================
    # MULTIPLE STUDENTS
    # ==========================================

    return JsonResponse({

        "success": True,

        "multiple": True,

        "students": results,

    })


# =========================================================
# HOME
# =========================================================

def home(request):
    return render(
        request,
        "fees/home.html"
    )


# =========================================================
# FEES STRUCTURE
# =========================================================

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
# =========================================================

def add_fee_structure(request):

    if request.method == "POST":

        FeeStructure.objects.create(
            student_class=request.POST.get("student_class", "").strip(),
            academic_year=request.POST.get(
                "academic_year",
                "2026/2027"
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
# =========================================================

def reports(request):
    return render(
        request,
        "fees/reports.html"
    )


# =========================================================
# CLASSES
# =========================================================

def classes(request):
    return render(
        request,
        "fees/classes.html"
    )

# =========================================================
# AJAX STUDENT LOOKUP
# =========================================================

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

            except (ValueError, IndexError):

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