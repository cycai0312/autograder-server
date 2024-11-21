from typing import TypedDict

from django.contrib.auth.models import User

SerializedUser = TypedDict('SerializedUser', {
    'pk': int,
    'username': str,
    'first_name': str,
    'last_name': str,
    'email': str,
    'is_superuser': bool
})


def serialize_user(user: User) -> SerializedUser:
    return {
        'pk': user.pk,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_superuser': user.is_superuser,
    }
