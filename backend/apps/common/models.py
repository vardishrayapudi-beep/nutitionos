import uuid

from django.db import models


class TimeStampedUUIDModel(models.Model):
    """Abstract base for every Nutrition OS table: UUID primary key + audit timestamps.

    UUIDs avoid guessable sequential ids in URLs, but they are identifiers, NOT security
    controls - authorization must always be enforced separately.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
