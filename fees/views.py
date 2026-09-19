from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.http import JsonResponse
from django.db import models
from django.utils import timezone

from .models import Student, SchoolSettings, FeeStructure, Payment, Bill,  BusFeeStructure, BusFeeRecord


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

        # Find matching fee structure
        student.fee_structure = FeeStructure.objects.filter(
            student_class=student.student_class,
            academic_year=student.academic_year
        ).first()


        # -----------------------------------------------
        # TOTAL FEE
        # -----------------------------------------------

        if student.fee_structure:

            student.total_fee = (
                student.fee_structure.total_fee
            )

        else:

            student.total_fee = 0


        # -----------------------------------------------
        # TOTAL PAID
        # -----------------------------------------------

        student.total_paid = Payment.objects.filter(
            student=student,
            academic_year=student.academic_year
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or 0


        # -----------------------------------------------
        # BALANCE
        # -----------------------------------------------

        student.calculated_balance = (
            student.total_fee - student.total_paid
        )


        # -----------------------------------------------
        # FEE STATUS
        # -----------------------------------------------

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


    # Get current academic year from School Settings
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
# =========================================================

# =========================================================
# STUDENT PROFILE
# =========================================================

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

    payments = Payment.objects.select_related(
        "student"
    ).all().order_by(
        "-payment_date",
        "-id"
    )

    # ==========================================
    # SEARCH
    # ==========================================

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


    # ==========================================
    # CLASS FILTER
    # ==========================================

    student_class = request.GET.get(
        "student_class",
        ""
    ).strip()

    if student_class:

        payments = payments.filter(
            student__student_class=student_class
        )


    # ==========================================
    # ACADEMIC YEAR FILTER
    # ==========================================

    academic_year = request.GET.get(
        "academic_year",
        ""
    ).strip()

    if academic_year:

        payments = payments.filter(
            academic_year=academic_year
        )


    # ==========================================
    # TERM FILTER
    # ==========================================

    term = request.GET.get(
        "term",
        ""
    ).strip()

    if term:

        payments = payments.filter(
            term=term
        )


    # ==========================================
    # PAYMENT METHOD FILTER
    # ==========================================

    payment_method = request.GET.get(
        "payment_method",
        ""
    ).strip()

    if payment_method:

        payments = payments.filter(
            payment_method=payment_method
        )


    # ==========================================
    # STATISTICS
    # ==========================================

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


    # ==========================================
    # FILTER OPTIONS
    # ==========================================

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

# =========================================================
# CREATE BILL
# =========================================================

def create_bill(request):

    if request.method == "POST":

        student_id = request.POST.get("student_id")
        academic_year = request.POST.get("academic_year")
        term = request.POST.get("term")
        discount_percent = request.POST.get("discount_percent", 0)

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
            student = Student.objects.get(id=student_id)
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
            discount_percent = float(discount_percent)
        except (TypeError, ValueError):
            discount_percent = 0

        if discount_percent < 0:
            discount_percent = 0

        if discount_percent > 100:
            discount_percent = 100

        discount_amount = (
            original_total * discount_percent / 100
        )

        amount_due = original_total - discount_amount

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

    return render(request, "fees/create_bill.html")

# =========================================================
# BILL FEE LOOKUP
# =========================================================

def bill_fee_lookup(request):

    student_id = request.GET.get("student_id")
    academic_year = request.GET.get("academic_year")
    term = request.GET.get("term")

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
        student = Student.objects.get(id=student_id)
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
                f"{student.student_class}, {academic_year}, {term}."
            )
        })

    # Original term fee
    original_total = fee_structure.total_fee

    # Current student discount
    discount_percent = student.discount or 0

    # Calculate discount
    discount_amount = (
        original_total * discount_percent / 100
    )

    # Final amount required
    amount_due = original_total - discount_amount

    # Payments made for THIS student, academic year and term
    total_paid = Payment.objects.filter(
        student=student,
        academic_year=academic_year,
        term=term
    ).aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    # Amount still owed
    amount_owed = amount_due - total_paid

    # Prevent negative balance
    if amount_owed < 0:
        amount_owed = 0

    return JsonResponse({
        "success": True,

        "student": {
            "id": student.id,
            "name": f"{student.first_name} {student.last_name}",
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

from datetime import date, timedelta


def bus_fees(request):

    selected_class = request.GET.get("student_class", "").strip()

    selected_date = request.GET.get("date", "").strip()

    if selected_date:
        try:
            current_date = date.fromisoformat(selected_date)
        except ValueError:
            current_date = date.today()
    else:
        current_date = date.today()

    # Find the Monday of the selected week
    monday = current_date - timedelta(days=current_date.weekday())

    # Monday to Friday
    week_dates = [
        monday + timedelta(days=i)
        for i in range(5)
    ]

    # Get available classes from students
    classes = (
        Student.objects
        .values_list("student_class", flat=True)
        .distinct()
        .order_by("student_class")
    )

    # Get students for selected class
    if selected_class:
        students = (
            Student.objects
            .filter(
                student_class=selected_class,
                status="Active"
            )
            .order_by("first_name", "last_name")
        )
    else:
        students = []

    context = {
        "selected_class": selected_class,
        "classes": classes,
        "students": students,
        "week_dates": week_dates,
        "monday": monday,
        "friday": week_dates[-1],
    }

    return render(
        request,
        "fees/bus_fees.html",
        context
    )