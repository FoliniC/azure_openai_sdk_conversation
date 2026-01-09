import sys


def test_debug_path():
    print("\nSYS PATH:", sys.path)
    try:
        import homeassistant

        print("HOMEASSISTANT FILE:", homeassistant.__file__)
        import homeassistant.helpers.typing

        print(
            "HOMEASSISTANT.HELPERS.TYPING FILE:", homeassistant.helpers.typing.__file__
        )
    except ImportError as e:
        print("IMPORT ERROR:", e)
