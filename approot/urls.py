from django.urls import path

from .views import (
    PayloadListCreateView,
    PayloadDetailView,
    DeviceListCreateView,
    DeviceDetailView,
)

urlpatterns = [
    path("payload/", PayloadListCreateView.as_view(), name="payload"),
    path("payload/<int:pk>/", PayloadDetailView.as_view(), name="payload-detail"),
    path("device/", DeviceListCreateView.as_view(), name="device-list"),
    path("device/<int:pk>/", DeviceDetailView.as_view(), name="device-detail"),
]
