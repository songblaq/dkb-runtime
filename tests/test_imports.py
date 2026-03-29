def test_import_main():
    from dkb_runtime.main import app

    assert app.title
