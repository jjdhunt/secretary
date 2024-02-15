def test_creating_database_when_none_exists():
    import sys
    sys.path.append('../secretary')

    from secretary import todo

    todo = todo.Todo('./tests/TEMP_TEST_database')
    todo.save_database()

    # clean up
    import os
    os.remove('./tests/TEMP_TEST_database')

