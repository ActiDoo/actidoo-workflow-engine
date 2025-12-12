from actidoo_wfe.wf.tests.helpers.dicts import are_dicts_equal


def test_dicts_equal_returns_true_given_same_dicts():
    dict1 = {"name": "John", "details": {"age": 30, "city": "New York"}}
    dict2 = {"name": "John", "details": {"age": 30, "city": "Los Angeles"}}
    dict2_same = {"details": {"age": 30, "city": "Los Angeles"}, "name": "John"}

    assert are_dicts_equal(dict2, dict2_same) is True

    assert are_dicts_equal(dict1, dict2) is False
    assert are_dicts_equal(dict2, dict1) is False

    assert are_dicts_equal(dict1, {}) is False
    assert are_dicts_equal({}, dict1) is False

    assert are_dicts_equal({}, {}) is True
