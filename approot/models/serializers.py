import base64
import binascii

from rest_framework import serializers

from . import Device, Payload
from ..constants import err_bad_base64


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["dev_eui", "name", "passing", "fcnt_latest"]


class PayloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payload
        fields = ["device", "data", "fcnt", "rx_info", "tx_info", "timestamp"]


class PayloadRequestSerializer(serializers.Serializer):
    devEUI = serializers.RegexField(r"^[0-9a-fA-F]{16}$")
    fCnt = serializers.IntegerField(min_value=0)
    data = serializers.CharField()
    rxInfo = serializers.ListField(child=serializers.DictField(), default=list)
    txInfo = serializers.DictField(default=dict)

    def validate_data(self, value):
        try:
            return base64.b64decode(value).hex()
        except binascii.Error as e:
            raise serializers.ValidationError(err_bad_base64(str(e)))
