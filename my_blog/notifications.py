from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from .models import Notification
from . import db

# নোটিফিকেশনের জন্য নতুন ব্লুপ্রিন্ট তৈরি করা হলো
notif_bp = Blueprint('notifications', __name__)

@notif_bp.route('/notifications')
@login_required
def view_notifications():
    """ব্যবহারকারীর সকল নোটিফিকেশন দেখানোর পেজ।"""
    
    # নোটিফিকেশন পেজ খুললেই সব অপঠিত নোটিফিকেশন পঠিত হয়ে যাবে
    notifications = current_user.notifications.order_by(Notification.created_at.desc()).all()
    
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifications)