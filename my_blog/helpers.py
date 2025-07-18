from datetime import date
from .models import DailyStat, Post
from . import db
from flask import flash, redirect, url_for, request
from flask_login import current_user
from functools import wraps
import re
import requests

def record_stat(stat_type):
    today = date.today()
    stats = DailyStat.query.filter_by(date=today).first()
    if not stats:
        stats = DailyStat(date=today)
        db.session.add(stats)

    if stat_type == 'user':
        if stats.new_users is None: stats.new_users = 0
        stats.new_users += 1
    elif stat_type == 'post':
        if stats.new_posts is None: stats.new_posts = 0
        stats.new_posts += 1
    elif stat_type == 'comment':
        if stats.new_comments is None: stats.new_comments = 0
        stats.new_comments += 1
    elif stat_type == 'like':
        if stats.new_likes is None: stats.new_likes = 0
        stats.new_likes += 1

    db.session.commit()

def check_banned(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.is_banned:
            flash("আপনার অ্যাকাউন্টটি ব্যান করা হয়েছে। আপনি এই কাজটি করতে পারবেন না।")
            return redirect(request.referrer or url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def create_unique_slug(title):
    slug = re.sub(r'[^\w]+', '-', title.lower()).strip('-')
    original_slug = slug
    counter = 1
    while Post.query.filter_by(slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1
    return slug

def upload_image_to_api(file_storage):
    """
    একটি ফাইলকে xneko API-তে আপলোড করে এবং URL রিটার্ন করে।
    """
    api_url = "https://xneko.pythonanywhere.com/photo"
    try:
        files = {'file': (file_storage.filename, file_storage.read(), file_storage.mimetype)}
        response = requests.post(api_url, files=files, timeout=60)

        if response.status_code == 200:
            data = response.json()
            return data.get('url')
        else:
            print(f"API Error: Status Code {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during API call: {e}")
        return None