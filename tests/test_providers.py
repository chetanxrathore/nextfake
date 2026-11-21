import nextfake


def test_import_and_version() -> None:
    assert nextfake.__version__ == "0.1.0"
