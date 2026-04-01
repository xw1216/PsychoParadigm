import random
from collections.abc import Sequence


def sample_jitter(time_range_s: Sequence[float], rng: random.Random) -> float:
    start, end = float(time_range_s[0]), float(time_range_s[1])
    return rng.uniform(start, end)


def balanced_binary_sequence(total_count: int, rng: random.Random) -> list[int]:
    sequence = [1] * (total_count // 2) + [0] * (total_count - total_count // 2)
    rng.shuffle(sequence)
    return sequence
