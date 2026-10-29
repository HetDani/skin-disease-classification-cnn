import os
import secrets
from PIL import Image, ImageOps
import requests
from flask import render_template, url_for, flash, redirect, request, abort, send_from_directory
from sdp import app, db, bcrypt, mail
from sdp.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             PostForm, RequestResetForm, ResetPasswordForm, UploadDetectionImage)
from sdp.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message

@app.route("/")
@app.route("/home")
def home():
    return render_template('index.html')

@app.route('/model.json')
def send_model():
    return app.send_static_file('js/model.json')

@app.route('/metadata.json')
def send_metadata():
    return app.send_static_file('js/metadata.json')

@app.route('/model.weights.bin')
def send_modelweights():
    return app.send_static_file('js/model.weights.bin')

@app.route("/realtimedetection")
@login_required
def realtimedetection():
    return render_template('realtimedetection.html', title='Realtime Disease Detection')

@app.route("/skindiseasedetect")
@login_required
def skindiseasedetect():
    return render_template('skindiseasedetect.html', title='Skin Disease Detection')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)

def save_picture_disease(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/disease_photos', picture_fn)

    i = Image.open(form_picture)
    i.save(picture_path)
    return picture_fn    


def classify_new(form_picture):
    
    data = {'location': form_picture}
    response = requests.post(url="http://127.0.0.1:5052/classify", params=data)
    resp = response.json()
    print(resp['class_name'])
    return resp['class_name']

@app.route("/detect_disease", methods=['GET', 'POST'])
@login_required
def detect_disease():
    form = UploadDetectionImage()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture_disease(form.picture.data)
            current_user.image_file = picture_file
        class_name  = classify_new(current_user.image_file)
        class_name = class_name[:-1]
        # return redirect(url_for('diseasename', classname = class_name, type='detect'))
        # accepted_strings = {'dermatitis', 'bullous', 'exanthems', 'alopecia', 'herpes', 'pigmentation', 'nail', 'poisonIvy', 'scabies'
        # 'systemic', 'tumors', 'vasculitis'}
        if class_name == 'error':
           return redirect(url_for('error', classname = class_name, type='detect'))
        else:
           return redirect(url_for(class_name, type='detect'))
        
    return render_template('detect_disease.html', title='Detect Skin Diseases',form=form)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)

@app.route('/acne', defaults={'type': 'detect'})
@app.route("/acne/<type>")
def acne(type):
    return render_template('disease_detect/acne.html', title='Acne',type = type)

@app.route('/actinic_keratosis', defaults={'type': 'detect'})
@app.route("/actinic_keratosis/<type>")
def actinic_keratosis(type):
    return render_template('disease_detect/actinic_keratosis.html', title='Actinic Keratosis',type = type)

@app.route('/basal_cell_carcinoma', defaults={'type': 'detect'})
@app.route("/basal_cell_carcinoma/<type>")
def basal_cell_carcinoma(type):
    return render_template('disease_detect/basal_cell_carcinoma.html', title='Basal Cell Carcinoma',type = type)

@app.route('/eczema', defaults={'type': 'detect'})
@app.route("/eczema/<type>")
def eczema(type):
    return render_template('disease_detect/eczema.html', title='Eczema',type = type)

@app.route('/error')
@app.route("/error")
def error(type):
    return render_template('disease_detect/error.html', title='Error')

@app.route('/melanoma', defaults={'type': 'detect'})
@app.route("/melanoma/<type>")
def melanoma(type):
    return render_template('disease_detect/melanoma.html', title='Melanoma',type = type)

@app.route('/psoriasis', defaults={'type': 'detect'})
@app.route("/psoriasis/<type>")
def psoriasis(type):
    return render_template('disease_detect/psoriasis.html', title='Psoriasis',type = type)

@app.route('/tinea_corporis', defaults={'type': 'detect'})
@app.route("/tinea_corporis/<type>")
def tinea_corporis(type):
    return render_template('disease_detect/tinea_corporis.html', title='Tinea Corporis',type = type)

@app.route('/rosacea', defaults={'type': 'detect'})
@app.route("/rosacea/<type>")
def rosacea(type):
    return render_template('disease_detect/rosacea.html', title='Rosacea',type = type)

@app.route('/herpes_zoster', defaults={'type': 'detect'})  
@app.route("/herpes_zoster/<type>")
def herpes_zoster(type):
    return render_template('disease_detect/herpes_zoster.html', title='Herpes Zoster',type = type)

@app.route('/cutaneous_horn', defaults={'type': 'detect'})  
@app.route("/cutaneous_horn/<type>")
def cutaneous_horn(type):
    return render_template('disease_detect/cutaneous_horn.html', title='Cutaneous Horn',type = type)

@app.route('/alopecia', defaults={'type': 'detect'})  
@app.route("/alopecia/<type>")
def alopecia(type):
    return render_template('disease_detect/alopecia.html', title='Alopecia',type = type)

@app.route('/molluscum', defaults={'type': 'detect'})  
@app.route("/molluscum/<type>")
def molluscum(type):
    return render_template('disease_detect/molluscum.html', title='Molluscum',type = type)

@app.route('/nail_diseases', defaults={'type': 'detect'})  
@app.route("/nail_diseases/<type>")
def nail_diseases(type):
    return render_template('disease_detect/nail_diseases.html', title='Nail Diseases',type = type)

@app.route('/normal_skin', defaults={'type': 'detect'})  
@app.route("/normal_skin/<type>")
def normal_skin(type):
    return render_template('disease_detect/normal_skin.html', title='Normal Skin',type = type)

@app.route('/normal_nail', defaults={'type': 'detect'})  
@app.route("/normal_nail/<type>")
def normal_nail(type):
    return render_template('disease_detect/normal_nail.html', title='Normal Nail',type = type)

@app.route('/diseasename', defaults={'classname': 'Disease', 'type': 'detect'})
@app.route("/diseasename/<classname>-<type>")
def diseasename(classname, type):
    return render_template('disease_detect/diseasename.html', title=classname,type = type)