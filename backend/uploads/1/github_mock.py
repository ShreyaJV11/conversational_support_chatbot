def login_user(token):
    if not token:
        return 'Token Expired'
    return 'Success'