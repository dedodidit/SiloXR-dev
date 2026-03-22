import math


SQRT_TWO = math.sqrt(2.0)
SQRT_TWO_PI = math.sqrt(2.0 * math.pi)


def phi(z: float) -> float:
    return math.exp(-0.5 * z * z) / SQRT_TWO_PI


def Phi(z: float) -> float:
    return 0.5 * math.erfc(-z / SQRT_TWO)


def compute_cv(mean: float, std: float) -> float:
    if mean == 0:
        return 1.0
    return std / mean


def get_distribution_params(mean: float, std: float, cv: float):
    if mean > 5 and cv < 0.5:
        adj_std = std
    else:
        adj_std = std * (1 + cv)
    return mean, adj_std


def expected_shortage(mean: float, std: float, stock: float) -> float:
    safe_std = max(float(std or 0.0), 1e-9)
    z = (float(stock or 0.0) - float(mean or 0.0)) / safe_std
    shortage = safe_std * phi(z) + (float(mean or 0.0) - float(stock or 0.0)) * (1.0 - Phi(z))
    return max(0.0, shortage)
