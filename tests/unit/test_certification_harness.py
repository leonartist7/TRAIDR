from scheduler.fault_injection import run_fault_injections


def test_shadow_fault_harness_recovers_public_stream_failures() -> None:
    results = run_fault_injections()

    assert results
    assert all(results.values())
