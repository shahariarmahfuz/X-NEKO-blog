from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, date

post_categories = db.Table('post_categories',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    bio = db.Column(db.Text, nullable=True) # নতুন: বায়ো যোগ করা হয়েছে
    profile_image_url = db.Column(db.String(256), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='User')
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text, nullable=True)

    posts = db.relationship('Post', backref='author', lazy='dynamic')
    comments = db.relationship('Comment', backref='commenter', lazy='dynamic')
    likes = db.relationship('Like', backref='liker', lazy='dynamic')
    notifications = db.relationship('Notification', foreign_keys='Notification.recipient_id', backref='recipient', lazy='dynamic')
    reports = db.relationship('Report', foreign_keys='Report.reporter_id', backref='reporter', lazy='dynamic')
    appeal = db.relationship('Appeal', backref='appellant', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='draft')
    is_hidden_by_ban = db.Column(db.Boolean, default=False)

    thumbnail_url = db.Column(db.String(256), nullable=True, default='default_thumbnail.png')
    view_count = db.Column(db.Integer, default=0)

    categories = db.relationship('Category', secondary=post_categories, backref=db.backref('posts', lazy='dynamic'), lazy='dynamic')
    tags = db.relationship('Tag', secondary=post_tags, backref=db.backref('posts', lazy='dynamic'), lazy='dynamic')
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade="all, delete-orphan")

    @hybrid_property
    def popularity_score(self):
        return self.likes.count() + (self.comments.count() * 2)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    is_hidden_by_ban = db.Column(db.Boolean, default=False)

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    post = db.relationship('Post', foreign_keys=[post_id])
    comment = db.relationship('Comment', foreign_keys=[comment_id])

class Appeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DailyStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, default=date.today)
    new_users = db.Column(db.Integer, default=0)
    new_posts = db.Column(db.Integer, default=0)
    new_comments = db.Column(db.Integer, default=0)
    new_likes = db.Column(db.Integer, default=0)