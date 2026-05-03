from receivers import Receiver, struct_fingerprint, telemetry_fingerprint


def _make_rx():
    rx = Receiver.__new__(Receiver)
    # Manually populate fields the fingerprints care about. We bypass __init__
    # because __init__ does a network probe.
    rx.station_id = "alpha"
    rx.station_url = "http://localhost/"
    rx.isActive = True
    rx.isAuto = True
    rx.isMobile = False
    rx.isSingle = False
    rx.inverted = False
    rx.latitude = 1.0
    rx.longitude = 2.0
    rx.heading = 3.0
    rx.doa = 4.0
    rx.doa_time = 5
    rx.power = 6.0
    rx.confidence = 7.0
    rx.frequency = 8.0
    return rx


def test_struct_fingerprint_stable_across_telemetry_change():
    a = _make_rx()
    b = _make_rx()
    b.doa = 999.0
    b.latitude = 999.0
    assert struct_fingerprint([a]) == struct_fingerprint([b])


def test_struct_fingerprint_changes_on_isActive_flip():
    a = _make_rx()
    b = _make_rx()
    b.isActive = False
    assert struct_fingerprint([a]) != struct_fingerprint([b])


def test_telemetry_fingerprint_changes_on_doa():
    a = _make_rx()
    b = _make_rx()
    b.doa = 4.5
    assert telemetry_fingerprint([a]) != telemetry_fingerprint([b])


def test_telemetry_fingerprint_stable_when_only_struct_changes():
    a = _make_rx()
    b = _make_rx()
    b.isAuto = False
    b.inverted = True
    assert telemetry_fingerprint([a]) == telemetry_fingerprint([b])
