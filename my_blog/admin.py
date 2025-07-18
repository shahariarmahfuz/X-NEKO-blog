from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import User, Post, Notification, Comment, Report, Appeal, DailyStat, Category
from . import db
from .decorators import admin_required, moderator_or_admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    users_pagination = User.query.order_by(User.id).paginate(page=page, per_page=10, error_out=False)

    pending_count = Post.query.filter_by(status='pending').count()
    report_count = Report.query.filter_by(status='pending').count()
    appeal_count = Appeal.query.filter_by(status='pending').count()
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        'admin_dashboard.html', 
        users_pagination=users_pagination, 
        pending_count=pending_count, 
        report_count=report_count, 
        appeal_count=appeal_count, 
        categories=categories
    )

@admin_bp.route('/moderator/dashboard')
@login_required
@moderator_or_admin_required
def moderator_dashboard():
    posts = Post.query.filter_by(status='pending').order_by(Post.created_at.desc()).all()
    return render_template('moderator_dashboard.html', posts=posts)


@admin_bp.route('/category/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    category_name = request.form.get('category_name')
    if category_name and not Category.query.filter_by(name=category_name).first():
        new_category = Category(name=category_name)
        db.session.add(new_category)
        db.session.commit()
        flash(f"ক্যাটাগরি '{category_name}' সফলভাবে যোগ করা হয়েছে।")
    else:
        flash("ক্যাটাগরি যোগ করা যায়নি। নামটি খালি অথবা আগে থেকেই موجود আছে।")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/approve/<int:post_id>')
@login_required
@moderator_or_admin_required
def approve_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.status = 'published'

    notification = Notification(
        recipient_id=post.author.id,
        message=f"আপনার '{post.title}' পোস্টটি অনুমোদন করা হয়েছে।",
        link=url_for('main.post', slug=post.slug)
    )
    db.session.add(notification)
    db.session.commit()
    flash(f"'{post.title}' পোস্টটি অনুমোদন করা হয়েছে।")
    return redirect(url_for('admin.moderator_dashboard'))

@admin_bp.route('/reject/<int:post_id>', methods=['POST'])
@login_required
@moderator_or_admin_required
def reject_post(post_id):
    post = Post.query.get_or_404(post_id)
    reason = request.form.get('reason', 'নির্দিষ্ট কোনো কারণ উল্লেখ করা হয়নি।')
    post.status = 'draft'

    notification = Notification(
        recipient_id=post.author.id,
        message=f"আপনার '{post.title}' পোস্টটি পর্যালোচনার পর ফেরত পাঠানো হয়েছে। কারণ: {reason}"
    )
    db.session.add(notification)
    db.session.commit()
    flash(f"পোস্টটি ব্যবহারকারীর কাছে ফেরত পাঠানো হয়েছে।")
    return redirect(url_for('admin.moderator_dashboard'))

@admin_bp.route('/preview_post/<int:post_id>')
@login_required
@moderator_or_admin_required
def preview_post(post_id):
    post = Post.query.get_or_404(post_id)
    top_level_comments = post.comments.filter_by(parent_id=None).order_by(Comment.created_at.asc()).all()
    return render_template('post.html', post=post, comments=top_level_comments, is_preview=True)

@admin_bp.route('/change_role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role in ['User', 'Moderator', 'Admin']:
        user.role = new_role
        db.session.commit()
        flash(f'{user.username}-এর ভূমিকা সফলভাবে পরিবর্তন করা হয়েছে।')
    else:
        flash('অবৈধ ভূমিকা।')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/reports')
@login_required
@admin_required
def view_reports():
    post_reports = Report.query.filter(Report.post_id != None, Report.status == 'pending').order_by(Report.created_at.desc()).all()
    comment_reports = Report.query.filter(Report.comment_id != None, Report.status == 'pending').order_by(Report.created_at.desc()).all()
    return render_template('reports.html', post_reports=post_reports, comment_reports=comment_reports)

@admin_bp.route('/report/dismiss/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def dismiss_report(report_id):
    report = Report.query.get_or_404(report_id)
    reason = request.form.get('reason', 'পর্যালোচনার পর এতে আপত্তিকর কিছু পাওয়া যায়নি।')
    report.status = 'reviewed'

    notification = Notification(
        recipient_id=report.reporter_id,
        message=f"আপনার রিপোর্টটি পর্যালোচনা করা হয়েছে। দুঃখিত, এতে কোনো সমস্যা পাওয়া যায়নি। কারণ: {reason}"
    )
    db.session.add(notification)
    db.session.commit()
    flash('রিপোর্টটি ডিসমিস করা হয়েছে।')
    return redirect(url_for('admin.view_reports'))

@admin_bp.route('/report/delete_content/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def delete_reported_content(report_id):
    report = Report.query.get_or_404(report_id)
    reason = request.form.get('reason', 'এটি আমাদের নীতিমালা লঙ্ঘন করেছে।')

    content_author_id = None
    reporter_id = report.reporter_id

    if report.post_id:
        post_to_delete = Post.query.get(report.post_id)
        if post_to_delete:
            content_author_id = post_to_delete.author.id

            # পোস্টের সাথে সম্পর্কিত সমস্ত রিপোর্ট ডিলিট করা হচ্ছে
            associated_reports = Report.query.filter_by(post_id=post_to_delete.id).all()
            for r in associated_reports:
                db.session.delete(r)

            db.session.delete(post_to_delete)
            flash(f"পোস্ট '{post_to_delete.title}' ডিলিট করা হয়েছে।")

    elif report.comment_id:
        comment_to_delete = Comment.query.get(report.comment_id)
        if comment_to_delete:
            content_author_id = comment_to_delete.commenter.id

            # কমেন্টের সাথে সম্পর্কিত সমস্ত রিপোর্ট ডিলিট করা হচ্ছে
            associated_reports = Report.query.filter_by(comment_id=comment_to_delete.id).all()
            for r in associated_reports:
                db.session.delete(r)

            db.session.delete(comment_to_delete)
            flash("কমেন্ট ডিলিট করা হয়েছে।")

    reporter_notification = Notification(
        recipient_id=reporter_id, 
        message="ধন্যবাদ! আপনার রিপোর্টের ভিত্তিতে আপত্তিকর বিষয়বস্তুটি সরিয়ে ফেলা হয়েছে।"
    )
    db.session.add(reporter_notification)

    if content_author_id:
        author_notification = Notification(
            recipient_id=content_author_id, 
            message=f"আপনার একটি বিষয়বস্তু রিপোর্টের ভিত্তিতে মুছে ফেলা হয়েছে। কারণ: {reason}"
        )
        db.session.add(author_notification)

    db.session.commit()
    return redirect(url_for('admin.view_reports'))

@admin_bp.route('/user/ban/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    reason = request.form.get('reason', 'নীতিমালা লঙ্ঘনের জন্য আপনাকে ব্যান করা হয়েছে।')

    user.is_banned = True
    user.ban_reason = reason

    Post.query.filter_by(user_id=user.id).update({'is_hidden_by_ban': True})
    Comment.query.filter_by(user_id=user.id).update({'is_hidden_by_ban': True})

    notification = Notification(recipient_id=user.id, message=f"আপনাকে ব্যান করা হয়েছে। কারণ: {reason}", link=url_for('main.appeal_ban'))
    db.session.add(notification)

    db.session.commit()
    flash(f"ব্যবহারকারী '{user.username}'-কে ব্যান করা হয়েছে।")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/user/unban/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.ban_reason = None

    Post.query.filter_by(user_id=user.id).update({'is_hidden_by_ban': False})
    Comment.query.filter_by(user_id=user.id).update({'is_hidden_by_ban': False})

    Appeal.query.filter_by(user_id=user.id, status='pending').update({'status':'reviewed'})

    notification = Notification(recipient_id=user.id, message="আপনার অ্যাকাউন্টটি পুনরায় সক্রিয় করা হয়েছে।")
    db.session.add(notification)
    db.session.commit()
    flash(f"ব্যবহারকারী '{user.username}'-কে আনব্যান করা হয়েছে।")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/appeals')
@login_required
@admin_required
def view_appeals():
    appeals = Appeal.query.filter_by(status='pending').all()
    return render_template('appeals.html', appeals=appeals)

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    stats = DailyStat.query.order_by(DailyStat.date.desc()).limit(30).all()
    return render_template('analytics.html', stats=stats)

@admin_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
@admin_required
def delete_comment(comment_id):
    comment_to_delete = Comment.query.get_or_404(comment_id)
    post_slug = comment_to_delete.post.slug

    # কমেন্টের সাথে সম্পর্কিত সমস্ত রিপোর্ট ডিলিট করা হচ্ছে
    associated_reports = Report.query.filter_by(comment_id=comment_to_delete.id).all()
    for r in associated_reports:
        db.session.delete(r)

    # এখন কমেন্টটি ডিলিট করা হচ্ছে
    db.session.delete(comment_to_delete)

    db.session.commit()
    flash("কমেন্টটি সফলভাবে ডিলিট করা হয়েছে।")
    return redirect(url_for('main.post', slug=post_slug))