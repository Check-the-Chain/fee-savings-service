from fee_savings_service.models import VolumeWindow


def test_window_values() -> None:
    assert VolumeWindow.ONE_DAY == "1d"
    assert VolumeWindow.SEVEN_DAYS == "7d"
    assert VolumeWindow.THIRTY_DAYS == "30d"
    assert VolumeWindow.ALL_TIME == "all"
