mock_inbox = [
    {
        "id": 1,
        "from": "user1@test.com",
        "subject": "UI issue",
        "body": "My dashboard UI is not working properly"
    },
    {
        "id": 2,
        "from": "user2@test.com",
        "subject": "Login problem",
        "body": "I am unable to login"
    }
]

def get_new_emails():
    return mock_inbox