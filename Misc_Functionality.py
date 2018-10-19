# Function that decides what the message is
def message_check(message):
    # Check to see if it is a token
    if len(message) == 128:
        return 0

    # Otherwise check to see is email
    elif '@lancaster.ac.uk' in message:
        return 1
    # Otherwise we don't know what to do with it for now
    else:
        return 2


# Function that counts the number of results returned from a mysql query
def count_results(results):
    count = 0

    for x in results:
        count += 1

    return count
