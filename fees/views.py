from django.shortcuts import render, redirect
from django.contrib.auth import logout


def logout_view(request):
    logout(request)
    return redirect("home")


def settings_view(request):
    return render(request, "fees/settings.html")


def students(request):
    return render(request, "fees/students.html")


def student_profile(request):
    return render(request, "fees/student_profile.html")


def add_student(request):
    return render(request, "fees/add_student.html")


def payments(request):
    return render(request, "fees/payments.html")

def record_payment(request):
    return render(request, "fees/record_payment.html")


def home(request):
    return render(request, "fees/home.html")


def fees_structure(request):
    return render(request, "fees/fees_structure.html")


def reports(request):
    return render(request, "fees/reports.html")


def classes(request):
    return render(request, "fees/classes.html")

