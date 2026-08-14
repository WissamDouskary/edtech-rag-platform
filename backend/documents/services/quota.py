from django.db.models import Sum

from ..models import Document


class QuotaExceededError(Exception):
    pass


def check_quota(user, additional_size_bytes):
    active_docs = Document.objects.filter(owner=user).exclude(status=Document.Status.FAILED)

    if active_docs.count() >= user.max_documents:
        raise QuotaExceededError(f"Nombre maximum de documents atteint ({user.max_documents}).")

    total_bytes = active_docs.aggregate(total=Sum("size_bytes"))["total"] or 0
    max_bytes = user.max_storage_mb * 1024 * 1024
    if total_bytes + additional_size_bytes > max_bytes:
        raise QuotaExceededError(f"Quota de stockage dépassé ({user.max_storage_mb} Mo).")
