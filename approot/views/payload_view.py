from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics
from django.db import transaction, IntegrityError

from ..auth import TokenAuthentication
from ..models import Device, Payload, PayloadSerializer, PayloadRequestSerializer


class PayloadDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payload.objects.all()
    serializer_class = PayloadSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = []


class PayloadListCreateView(generics.ListCreateAPIView):
    queryset = Payload.objects.all()
    serializer_class = PayloadSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = []

    def create(self, request, *args, **kwargs):
        # Validate payload
        serializer = PayloadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get payload
        payload = serializer.validated_data

        dev_eui = payload["devEUI"]
        received_fcnt = payload["fCnt"]
        rx_info = payload.get("rxInfo", [])
        tx_info = payload.get("txInfo", {})
        data_hex = payload["data"]

        # Check if passing
        passing = data_hex == "01"

        # Get device and update DB
        with transaction.atomic():
            device, _ = Device.objects.select_for_update().get_or_create(
                dev_eui=dev_eui, defaults={"fcnt_latest": -1, "passing": True}
            )

            # Replay/duplicate guard
            if received_fcnt <= device.fcnt_latest:
                return Response(
                    {
                        "status": "duplicate",
                        "received_fcnt": received_fcnt,
                        "device_latest_fcnt": device.fcnt_latest,
                    },
                    status=status.HTTP_200_OK,
                )

            # Create Payload object
            try:
                Payload.objects.create(
                    device=device,
                    data=data_hex,
                    fcnt=received_fcnt,
                    rx_info=rx_info,
                    tx_info=tx_info,
                )
            except IntegrityError:  # Meta level fcnt check
                return Response(
                    {
                        "status": "duplicate",
                        "received_fcnt": received_fcnt,
                        "device_latest_fcnt": device.fcnt_latest,
                    },
                    status=status.HTTP_200_OK,
                )

            # Update device
            device.fcnt_latest = received_fcnt
            device.passing = passing
            device.save(update_fields=["fcnt_latest", "passing"])

        return Response(
            {
                "devEUI": dev_eui,
                "fCnt": received_fcnt,
                "data": data_hex,
                "passing": passing,
            },
            status=status.HTTP_201_CREATED,
        )
