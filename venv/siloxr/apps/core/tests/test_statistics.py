from apps.core.statistics import compute_cv, expected_shortage, get_distribution_params


def test_compute_cv_returns_one_when_mean_is_zero():
    assert compute_cv(0, 5) == 1.0


def test_compute_cv_handles_cv_above_one_exactly():
    assert compute_cv(10, 25) == 2.5


def test_get_distribution_params_keeps_std_for_stable_demand():
    assert get_distribution_params(10, 2, 0.2) == (10, 2)


def test_get_distribution_params_expands_std_for_low_data_case():
    assert get_distribution_params(4, 2, 0.5) == (4, 3.0)


def test_expected_shortage_with_zero_stock_matches_mean_loss():
    assert round(expected_shortage(10, 2, 0), 6) == 10.0


def test_expected_shortage_is_stable_for_low_stock_case():
    assert round(expected_shortage(8, 4, 5), 6) == 3.524668


def test_expected_shortage_handles_high_cv_case():
    assert round(expected_shortage(3, 6, 1), 6) == 3.525417
