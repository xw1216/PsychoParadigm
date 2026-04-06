def build_test_marker_sequence(start_code: int, end_code: int) -> list[int]:
    if not 1 <= start_code <= 255:
        raise ValueError("start_code must be between 1 and 255")
    if not 1 <= end_code <= 255:
        raise ValueError("end_code must be between 1 and 255")
    if end_code < start_code:
        raise ValueError("end_code must be greater than or equal to start_code")
    return list(range(start_code, end_code + 1))