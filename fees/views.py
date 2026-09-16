from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout

from .models import Student, SchoolSettings, FeeStructure


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
    return render(
        request,
        "fees/record_payment.html"
    )


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