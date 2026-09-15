from django.db import models


class Student(models.Model):

    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
    ]

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    ]

    FEE_STATUS_CHOICES = [
        ("Paid", "Paid"),
        ("Pending", "Pending"),
        ("Overdue", "Overdue"),
    ]

    first_name = models.CharField(max_length=100)

    last_name = models.CharField(max_length=100)

    student_id = models.CharField(
        max_length=50,
        unique=True
    )

    registration_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )

    date_of_birth = models.DateField(
        blank=True,
        null=True
    )

    student_class = models.CharField(
        max_length=100
    )

    stream = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    academic_year = models.CharField(
        max_length=20,
        default="2025/2026"
    )

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES
    )

    parent_name = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    parent_contact = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    additional_information = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="Active"
    )

    fee_status = models.CharField(
        max_length=10,
        choices=FEE_STATUS_CHOICES,
        default="Pending"
    )

    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    photo = models.ImageField(
        upload_to="students/",
        blank=True,
        null=True
    )

    date_registered = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"