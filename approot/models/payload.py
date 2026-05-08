from django.db import models

from approot.models import Device


class Payload(models.Model):
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="payloads"
    )
    data = models.CharField(max_length=512)  # Parsed hexadecimal value
    fcnt = models.IntegerField()

    # Extra metadata; a separate metadata class can be defined if we want to complex queries on rx and tx info
    rx_info = models.JSONField(default=list, blank=True)
    tx_info = models.JSONField(default=dict, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("device", "fcnt")
        ordering = ["-timestamp"]
