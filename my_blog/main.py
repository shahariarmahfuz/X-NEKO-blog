import os
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash, current_app, jsonify
from flask_login import login_required, current_user
from .models import Post, Category, User, Like, Comment, Notification, Tag, Report, Appeal
from . import db
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func, or_
from .helpers import record_stat, check_banned, create_unique_slug, upload_image_to_api

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)

    recent_posts_pagination = Post.query.filter_by(status='published', is_hidden_by_ban=False)\
                                    .order_by(Post.created_at.desc())\
                                    .paginate(page=page, per_page=10, error_out=False)

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    trending_posts_query = db.session.query(Post, func.count(Like.id).label('total_likes'))\
                                .join(Like, Post.id == Like.post_id)\
                                .filter(Post.status=='published', Post.created_at >= seven_days_ago, Post.is_hidden_by_ban==False)\
                                .group_by(Post)\
                                .order_by(func.count(Like.id).desc())\
                                .limit(3).all()
    trending_posts = [post for post, like_count in trending_posts_query]

    all_posts = Post.query.filter_by(status='published', is_hidden_by_ban=False).all()
    best_posts = sorted(all_posts, key=lambda p: p.popularity_score, reverse=True)[:3]

    return render_template('index.html',
                           posts_pagination=recent_posts_pagination,
                           trending_posts=trending_posts,
                           best_posts=best_posts)

@main_bp.route('/post/<string:slug>')
def post(slug):
    post_to_view = Post.query.filter_by(slug=slug, status='published', is_hidden_by_ban=False).first_or_404()

    post_to_view.view_count = (post_to_view.view_count or 0) + 1
    db.session.commit()

    top_level_comments = post_to_view.comments.filter_by(parent_id=None, is_hidden_by_ban=False).order_by(Comment.created_at.asc()).all()

    related_popular_posts = []
    primary_category = post_to_view.categories.first()
    if primary_category:
        related_popular_posts = Post.query.join(Post.categories)\
            .filter(
                Category.id == primary_category.id,
                Post.id != post_to_view.id,
                Post.status == 'published',
                Post.is_hidden_by_ban == False
            ).order_by(Post.view_count.desc()).limit(5).all()


    return render_template('post.html', post=post_to_view, comments=top_level_comments, related_popular_posts=related_popular_posts)

@main_bp.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    if not query:
        return redirect(url_for('main.index'))

    search_query = f'%{query}%'
    search_results = Post.query.filter(
        or_(Post.title.ilike(search_query), Post.content.ilike(search_query)),
        Post.status == 'published',
        Post.is_hidden_by_ban == False
    ).order_by(Post.created_at.desc()).paginate(page=page, per_page=10, error_out=False)

    return render_template('search_results.html', query=query, results_pagination=search_results)

@main_bp.route('/categories')
def all_categories():
    page = request.args.get('page', 1, type=int)
    categories_pagination = Category.query.order_by(Category.name).paginate(page=page, per_page=20, error_out=False)
    return render_template('all_categories.html', categories_pagination=categories_pagination)

@main_bp.route('/category/<string:category_name>')
def category_posts(category_name):
    page = request.args.get('page', 1, type=int)
    category = Category.query.filter_by(name=category_name).first_or_404()

    posts_pagination = category.posts.filter_by(status='published', is_hidden_by_ban=False)\
                                    .order_by(Post.created_at.desc())\
                                    .paginate(page=page, per_page=10, error_out=False)

    return render_template('category_posts.html', category=category, posts_pagination=posts_pagination)


@main_bp.route('/my-posts')
@login_required
def my_posts():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    query = Post.query.filter_by(author=current_user)

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    posts_pagination = query.order_by(Post.updated_at.desc()).paginate(page=page, per_page=5)

    return render_template('my_posts_management.html', posts_pagination=posts_pagination, status_filter=status_filter)

@main_bp.route('/new-post', methods=['GET'])
@login_required
@check_banned
def new_post():
    title = "নতুন শিরোনাম"
    slug = create_unique_slug(title)
    new_post = Post(title=title, content="", author=current_user, slug=slug)
    db.session.add(new_post)
    db.session.commit()
    record_stat('post')
    return redirect(url_for('main.edit_post', post_id=new_post.id))

# ---- পরিবর্তিত এবং নিরাপদ edit_post ফাংশন ----
@main_bp.route('/edit-post/<int:post_id>', methods=['GET', 'POST'])
@login_required
@check_banned
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user and current_user.role not in ['Admin', 'Moderator']:
        abort(403)

    if request.method == 'POST':
        try:
            new_title = request.form.get('title')
            if new_title != post.title:
                post.slug = create_unique_slug(new_title)
            post.title = new_title

            post.content = request.form.get('content')

            # ক্যাটাগরি আপডেট
            post.categories = []
            category_id = request.form.get('category')
            if category_id:
                category = Category.query.get(category_id)
                if category:
                    post.categories.append(category)

            # ট্যাগ আপডেট
            post.tags = []
            tags_str = request.form.get('tags', '')
            if tags_str:
                tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]
                for tag_name in tag_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    post.tags.append(tag)

            # থাম্বনেইল আপলোড
            if 'thumbnail' in request.files:
                file = request.files['thumbnail']
                if file and file.filename != '':
                    flash("ছবি আপলোড করা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")
                    image_url = upload_image_to_api(file)
                    if image_url:
                        post.thumbnail_url = image_url
                        flash("থাম্বনেইল সফলভাবে আপলোড হয়েছে।")
                    else:
                        flash("দুঃখিত, ছবিটি আপলোড করা যায়নি।")

            # স্ট্যাটাস পরিবর্তন
            publish_option = request.form.get('publish_option')
            if publish_option == 'draft':
                post.status = 'draft'
            elif publish_option == 'publish':
                if not post.thumbnail_url or post.thumbnail_url == 'default_thumbnail.png':
                    flash("পোস্ট পাবলিশ করার জন্য অবশ্যই একটি থাম্বনেইল আপলোড করতে হবে।")
                    return redirect(url_for('main.edit_post', post_id=post.id))
                post.status = 'pending'

            # সেশনে থাকা পরিবর্তন কমিট করা
            db.session.commit()
            flash('পোস্ট সফলভাবে আপডেট করা হয়েছে।')
            return redirect(url_for('main.my_posts'))

        except Exception as e:
            db.session.rollback() # কোনো ইরর হলে সেশন রোলব্যাক করা
            flash(f"একটি ইরর হয়েছে: {e}")
            return redirect(url_for('main.edit_post', post_id=post.id))

    # GET রিকোয়েস্টের জন্য
    categories = Category.query.all()
    tags_str = ', '.join([tag.name for tag in post.tags])
    return render_template('edit_post.html', post=post, categories=categories, tags_str=tags_str)

@main_bp.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
@check_banned
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("পোস্ট সফলভাবে ডিলিট করা হয়েছে।")
    return redirect(url_for('main.my_posts'))

@main_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
@check_banned
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(liker=current_user, post=post).first()

    user_liked = False
    if like:
        db.session.delete(like)
        user_liked = False
    else:
        new_like = Like(liker=current_user, post=post)
        db.session.add(new_like)
        record_stat('like')
        user_liked = True
        if post.author != current_user:
            notification = Notification(recipient_id=post.author.id, message=f"'{current_user.username}' আপনার '{post.title}' পোস্টে লাইক দিয়েছেন।", link=url_for('main.post', slug=post.slug))
            db.session.add(notification)

    db.session.commit()

    return jsonify({
        'success': True,
        'user_liked': user_liked,
        'likes_count': post.likes.count()
    })

@main_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
@check_banned
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    comment_text = request.form.get('comment_text')
    parent_id = request.form.get('parent_id')

    if comment_text:
        new_comment = Comment(text=comment_text, commenter=current_user, post=post, parent_id=int(parent_id) if parent_id else None)
        db.session.add(new_comment)
        record_stat('comment')
        if post.author != current_user:
            notification = Notification(recipient_id=post.author.id, message=f"'{current_user.username}' আপনার '{post.title}' পোস্টে কমেন্ট করেছেন।", link=url_for('main.post', slug=post.slug, _anchor=f'comment-{new_comment.id}'))
            db.session.add(notification)
        db.session.commit()

    return redirect(url_for('main.post', slug=post.slug))

@main_bp.route('/report', methods=['POST'])
@login_required
@check_banned
def submit_report():
    reason = request.form.get('reason')
    post_id = request.form.get('post_id')
    comment_id = request.form.get('comment_id')

    if not reason:
        flash("রিপোর্ট করার জন্য একটি কারণ উল্লেখ করতে হবে।")
    else:
        report = Report(reason=reason, reporter=current_user, post_id=int(post_id) if post_id else None, comment_id=int(comment_id) if comment_id else None)
        db.session.add(report)
        db.session.commit()
        flash("আপনার রিপোর্টটি পর্যালোচনার জন্য জমা দেওয়া হয়েছে।")

    if post_id:
        post = Post.query.get(post_id)
        return redirect(url_for('main.post', slug=post.slug))
    elif comment_id:
        comment = Comment.query.get(comment_id)
        return redirect(url_for('main.post', slug=comment.post.slug))

    return redirect(url_for('main.index'))

@main_bp.route('/appeal', methods=['GET', 'POST'])
@login_required
def appeal_ban():
    if not current_user.is_banned:
        return redirect(url_for('main.index'))

    existing_appeal = Appeal.query.filter_by(user_id=current_user.id, status='pending').first()
    if existing_appeal:
        flash("আপনার একটি আপিল ইতিমধ্যে পর্যালোচনার জন্য জমা আছে।")
        return render_template('appeal_form.html', appeal_exists=True)

    if request.method == 'POST':
        reason = request.form.get('reason')
        if reason:
            new_appeal = Appeal(user_id=current_user.id, reason=reason)
            db.session.add(new_appeal)
            db.session.commit()
            flash("আপনার আপিলটি জমা দেওয়া হয়েছে। এডমিন এটি পর্যালোচনা করবেন।")
            return redirect(url_for('main.index'))

    return render_template('appeal_form.html', appeal_exists=False)

@main_bp.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    recent_posts = user.posts.filter_by(status='published', is_hidden_by_ban=False).order_by(Post.created_at.desc()).limit(5).all()
    return render_template('profile.html', user=user, recent_posts=recent_posts)

@main_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = current_user
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')

        if new_username != user.username and User.query.filter_by(username=new_username).first():
            flash('এই ইউজারনেমটি অন্য কেউ ব্যবহার করছে।')
            return redirect(url_for('main.edit_profile'))

        if new_email != user.email and User.query.filter_by(email=new_email).first():
            flash('এই ইমেইলটি অন্য কেউ ব্যবহার করছে।')
            return redirect(url_for('main.edit_profile'))

        user.full_name = request.form.get('full_name')
        user.username = new_username
        user.email = new_email
        user.bio = request.form.get('bio')

        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                flash("প্রোফাইল ছবি আপলোড করা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")
                image_url = upload_image_to_api(file)
                if image_url:
                    user.profile_image_url = image_url
                    flash("প্রোফাইল ছবি সফলভাবে আপডেট করা হয়েছে।")
                else:
                    flash("দুঃখিত, প্রোফাইল ছবিটি আপলোড করা যায়নি।")

        db.session.commit()
        flash('আপনার প্রোফাইল সফলভাবে আপডেট করা হয়েছে।')
        return redirect(url_for('main.profile', username=user.username))

    return render_template('edit_profile.html', user=user)

@main_bp.route('/user/<username>/posts')
@login_required
def user_posts(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user, status='published', is_hidden_by_ban=False).order_by(Post.created_at.desc()).all()
    return render_template('user_posts.html', user=user, posts=posts)