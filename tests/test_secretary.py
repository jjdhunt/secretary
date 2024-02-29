def test_extracting_a_simple_todo():
    import pandas as pd
    import sys
    sys.path.append('../secretary')

    import secretary.secretary_bot as sb

    message_content = "Silvia needs to buy eggs by 10/03/2022."
    message = "From: Jack\n" + message_content

    df = sb.extract_tasks(message)

    date_string = "2022-10-03"

    # gpt should capture the whole message contents as notes since it is short.
    assert df.loc[0, 'notes'] == message_content

    # gpt should extract the due date.
    assert df.loc[0, 'due date'] == date_string

    # gpt should extract the requestor
    assert df.loc[0, 'requestor'] == 'Jack'

    # gpt should extract the actor
    assert df.loc[0, 'actor'] == 'Silvia'

    
def test_inferring_a_date():
    import pandas as pd
    import sys
    sys.path.append('../secretary')

    import secretary.secretary_bot as sb

    message = "I need to buy eggs before next Wednesday."

    today = "2024-02-11" # A Sunday
    next_wednesday = "2024-02-14"
    df = sb.extract_tasks(message, current_datetime_string=today)

    # gpt should capture the whole message notes since it is short.
    assert df.loc[0, 'notes'] == message

    # gpt Should infer the due date for "next Wednesday".
    assert df.loc[0, 'due date'] == next_wednesday

def test_question_answering():
    import sys
    sys.path.append('../secretary')
    from secretary import todo
    import secretary.secretary_bot as sb

    comment = 'From: Jack\nHow many "steves estate" tasks are open?'

    todos = todo.Todo('tests/data/tasks_database')
    similar_tasks_json = todos.get_similar_tasks_as_json(comment, 0.3)
    answer = sb.answer_questions_about_tasks(comment, similar_tasks_json, current_datetime_string="2024-02-11")
    assert (
        '6' in answer or
        'six' in answer
    )