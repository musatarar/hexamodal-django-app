from django.db import models

DEV_EUI_LENGTH = 16


class Device(models.Model):
    dev_eui = models.CharField(  # Unique device ID
        max_length=DEV_EUI_LENGTH, unique=True, db_index=True
    )
    name = models.CharField(max_length=100, default="")  # Device name
    passing = models.BooleanField(
        default=True
    )  # Status passing if True, failing if False
    fcnt_latest = models.IntegerField(default=-1)  # Increments with each payload

    @property
    def status(self):
        return "passing" if self.passing else "failing"
