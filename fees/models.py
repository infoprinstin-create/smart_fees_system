
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

    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
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


class SchoolSettings(models.Model):

    school_name = models.CharField(
        max_length=200,
        default="School Name"
    )

    logo = models.ImageField(
        upload_to="school/",
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    academic_year = models.CharField(
        max_length=20,
        default="2026/2027"
    )

    school_motto = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.school_name

class FeeStructure(models.Model):

    TERM_CHOICES = [
        ("First Term", "First Term"),
        ("Second Term", "Second Term"),
        ("Third Term", "Third Term"),
    ]

    student_class = models.CharField(max_length=100)

    academic_year = models.CharField(
        max_length=20,
        default="2026/2027"
    )

    term = models.CharField(
        max_length=20,
        choices=TERM_CHOICES
    )

    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    tuition_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    examination_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    library_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    activity_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    @property
    def total_fee(self):

        return (
            self.registration_fee
            + self.tuition_fee
            + self.examination_fee
            + self.library_fee
            + self.activity_fee
        )

    def __str__(self):

        return (
            f"{self.student_class} - "
            f"{self.academic_year} - "
            f"{self.term}"
        )

class Payment(models.Model):

    TERM_CHOICES = [
        ("First Term", "First Term"),
        ("Second Term", "Second Term"),
        ("Third Term", "Third Term"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("Cash", "Cash"),
        ("Bank Transfer", "Bank Transfer"),
        ("Mobile Money", "Mobile Money"),
        ("Cheque", "Cheque"),
        ("Card", "Card"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    academic_year = models.CharField(
        max_length=20
    )

    term = models.CharField(
        max_length=20,
        choices=TERM_CHOICES
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES
    )

    payment_date = models.DateField()

    receipt_number = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.amount} - "
            f"{self.academic_year}"
        )

class Bill(models.Model):

    TERM_CHOICES = [
        ("First Term", "First Term"),
        ("Second Term", "Second Term"),
        ("Third Term", "Third Term"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="bills"
    )

    academic_year = models.CharField(max_length=20)

    term = models.CharField(
        max_length=20,
        choices=TERM_CHOICES
    )

    # Original amount before discount
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Discount that was active when this bill was created
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    # Actual money removed because of the discount
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Final amount the student is required to pay
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
            return (
            f"{self.student} - "
            f"{self.academic_year} - "
            f"{self.term}"
        )