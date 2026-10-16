"""Hostname recommendations use observed hardware and preserve device identity."""

import pytest

from backend.models import Device
from backend.services.device_discovery import enrich_from_scan


def observe(report):
    device = Device(hostname="inventory-name", endpoint="192.0.2.10", kind="generic")
    device.annotations = {"rack": "lab"}
    enrich_from_scan(device, report)
    assert device.hostname == "inventory-name"
    assert device.endpoint == "192.0.2.10"
    assert device.annotations == {"rack": "lab"}
    return device


@pytest.mark.parametrize("identity,model", [
    ({"product_name": "NVIDIA DGX Spark", "architecture": "aarch64"}, "spark"),
    ({"product_name": "GX10", "architecture": "aarch64", "gpu_model": "NVIDIA GB10"}, "spark"),
    ({"product_name": "DGX H100"}, "dgx"),
    ({"product_name": "NVIDIA DGX Station"}, "dgx"),
    ({"dgx_name": "DGX A100"}, "dgx"),
    ({"product_name": "NVIDIA Jetson AGX Orin Developer Kit"}, "jetson"),
    ({"product_name": "NA", "device_tree_model": "NVIDIA Jetson Nano Developer Kit\x00"}, "jetson"),
])
def test_recommendation_uses_model_and_last_six_serial_characters(identity, model):
    device = observe({**identity, "motherboard_serial": "  P123 AB\tC456\n"})
    assert device.facts["recommended_hostname"] == f"ai-sae-{model}-abc456"
    assert device.facts["hostname_recommendation_source"] == "Baseboard serial number"
    assert device.facts["hostname_recommendation_reason"] is None
    assert device.facts["motherboard"]["serial"] == "P123ABC456"


@pytest.mark.parametrize("serial", [
    None, "", "unknown", "NA", "N/A", "Not Specified", "Not Available",
    "To Be Filled By O.E.M.", "Default string", "System Serial Number", "Serial Number",
    "00000000", "FFFFFFFF", "12345", "123456!", "123-456", "12345é",
    "$(touch /tmp/oops)123456", "x" * 161,
])
def test_unusable_serial_never_produces_a_hostname(serial):
    device = observe({"product_name": "DGX H100", "motherboard_serial": serial})
    assert device.facts["recommended_hostname"] is None
    assert device.facts["hostname_recommendation_source"] is None
    assert "No usable hardware serial" in device.facts["hostname_recommendation_reason"]


@pytest.mark.parametrize("identity", [
    {}, {"product_name": "PowerEdge R760xa", "gpu_model": "NVIDIA H100"},
    {"product_name": "Workstation"}, {"product_name": "DGX Spark", "architecture": "x86_64"},
    {"product_name": "Not a DGX Spark"}, {"product_name": "Jetson-compatible board"},
    {"product_name": "ARM Developer Kit", "architecture": "aarch64"},
])
def test_unsupported_hardware_does_not_guess_from_gpu_or_architecture(identity):
    device = observe({**identity, "motherboard_serial": "ABC123456"})
    assert device.facts["recommended_hostname"] is None
    assert "Model was not identified" in device.facts["hostname_recommendation_reason"]


def test_jetson_fallback_is_labeled_and_baseboard_takes_precedence():
    report = {"device_tree_model": "NVIDIA Jetson AGX Orin\x00", "product_name": "unknown",
              "device_tree_serial": "1234567890123\x00", "motherboard_serial": "Default string"}
    device = observe(report)
    assert device.model == "NVIDIA Jetson AGX Orin"
    assert device.facts["recommended_hostname"] == "ai-sae-jetson-890123"
    assert device.facts["hostname_recommendation_source"] == "Jetson device tree serial number"
    report["motherboard_serial"] = "BOARD-ABC456"
    enrich_from_scan(device, report)
    assert device.facts["recommended_hostname"] == "ai-sae-jetson-abc456"
    assert device.facts["hostname_recommendation_source"] == "Baseboard serial number"


def test_dgx_does_not_fall_back_to_a_different_serial_source():
    device = observe({"product_name": "DGX H100", "device_tree_serial": "123456789"})
    assert device.facts["recommended_hostname"] is None


def test_new_scan_clears_old_recommendation_when_serial_disappears():
    device = observe({"product_name": "DGX H100", "motherboard_serial": "123456789"})
    assert device.facts["recommended_hostname"] == "ai-sae-dgx-456789"
    enrich_from_scan(device, {"product_name": "DGX H100"})
    assert device.facts["recommended_hostname"] is None
    assert device.facts["motherboard"]["serial"] is None
