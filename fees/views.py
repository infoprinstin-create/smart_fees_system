
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout

from .models import Student


def logout_view(request):
    logout(request)
    return redirect("home")


def settings_view(request):
    return render(request, "fees/settings.html")


# =========================================================
# STUDENTS
# =========================================================

def students(request):

    students = Student.objects.all().order_by("-date_registered")

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

    return render(
        request,
        "fees/student_profile.html",
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
    return render(
        request,
        "fees/fees_structure.html"
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

