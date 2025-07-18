from flask import Blueprint, render_template, request, redirect, url_for, flash
from .models import User
from . import db
from flask_login import login_user, logout_user
from .helpers import record_stat

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('এই ইউজারনেমটি আগে থেকেই আছে।')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('এই ইমেইলটি আগে থেকেই ব্যবহৃত হচ্ছে।')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email, full_name=full_name, role='User')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        record_stat('user')

        flash('রেজিস্ট্রেশন সফল হয়েছে। এখন লগইন করুন।')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('ভুল ইউজারনেম বা পাসওয়ার্ড।')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))