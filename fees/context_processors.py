from .models import SchoolSettings


def school_settings(request):

    settings = SchoolSettings.objects.first()

    if not settings:
        settings = SchoolSettings.objects.create()

    return {
        "school_settings": settings
    }