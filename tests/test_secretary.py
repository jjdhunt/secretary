def test_extracting_a_simple_todo():
    import pandas as pd
    import sys
    sys.path.append('../secretary')

    import secretary.secretary_bot as sb

    message_content = "Silvia needs to buy eggs by 10/03/2022."
    message = "From: Jack\n" + message_content

    df = sb.extract_tasks(message)

    date_string = "2022-10-03 00:00:00"
    datetime_object = pd.to_datetime(date_string)

    # gpt should capture the whole message contents as details since it is short.
    assert df.loc[0, 'details'] == message_content

    # gpt should extract the date.
    assert df.loc[0, 'date'] == datetime_object

    # gpt should extract the requestor
    assert df.loc[0, 'requestor'] == 'Jack'

    # gpt should extract the actor
    assert df.loc[0, 'actor'] == 'Silvia'

    
def test_inferring_a_date():
    import pandas as pd
    import sys
    sys.path.append('../secretary')

    import secretary.secretary_bot as sb

    message = "I need to buy eggs by before next Wednesday."

    today = "2024-02-11 00:00:00" # A Sunday
    next_wednesday = "2024-02-14 00:00:00"
    df = sb.extract_tasks(message, current_datetime_string=today)

    # gpt should capture the whole message details since it is short.
    assert df.loc[0, 'details'] == message

    # gpt Should infer the date for "next Wednesday".
    assert df.loc[0, 'date'] == pd.to_datetime(next_wednesday) 