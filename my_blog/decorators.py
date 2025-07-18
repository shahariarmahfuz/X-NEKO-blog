from functools import wraps
from flask_login import current_user
from flask import abort

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def moderator_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['Moderator', 'Admin']:
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def author_or_higher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['Author', 'Moderator', 'Admin']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function