from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail,Message
from . import app
from flask import render_template, url_for, Markup
from random import randint
from datetime import datetime
import hashlib
import os
from lxml.html.clean import Cleaner
import pytz
import re
import pymssql
import csv
from functools import wraps
from flask import request, Response


mail = Mail(app)
ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])

def ConnectDataLogDB():
    dbconf = app.config['DATA_LOG_DB']
    return pymssql.connect(dbconf['server'], dbconf['user'], dbconf['password'], dbconf['dbname'], charset="utf8")

def QueryDataLogHistory(csv_handle, task, resource_table, batch_no):
    conn = ConnectDataLogDB()
    cursor = conn.cursor()
    cursor.execute("SELECT DataLogHistory.batch_no, DataLogHistory.create_time, DataLogHistory.state, resource_table, resource_id, DataLogHistory.resource_content, source_url, source_content FROM DataLogHistory JOIN DataLog ON DataLogHistory.data_log_id = DataLog.ID WHERE DataLogHistory.batch_no = %s AND resource_table = %s", (batch_no, resource_table))
    for row in cursor:
        csv_handle.writerow([task] + list(row))
    conn.close()

def QueryDataLogAnomaly(csv_handle, task, resource_table, batch_no):
    conn = ConnectDataLogDB()
    cursor = conn.cursor()
    cursor.execute("SELECT DataLogHistory.batch_no, DataLogHistory.create_time, resource_table, resource_id, DataLogAnomaly.type, column_name, column_content, comment FROM DataLogAnomaly, DataLogHistory, DataLog WHERE DataLogAnomaly.data_log_history_id = DataLogHistory.ID AND DataLogHistory.data_log_id = DataLog.ID AND DataLogHistory.batch_no = %s AND resource_table = %s", (batch_no, resource_table))
    for row in cursor:
        csv_handle.writerow([task] + list(row))
    conn.close()


def rand_str():
    random_num = randint(100000,999999)
    raw_str = str(datetime.utcnow()) + str(randint(100000,999999))
    hash_fac = hashlib.new('ripemd160')
    hash_fac.update(raw_str.encode('utf-8'))
    return hash_fac.hexdigest()


def send_confirm_mail(email):
    subject = 'Confirm your email.'
    token = ts.dumps(email, salt='email-confirm-key')

    confirm_url = url_for(
        'home.confirm_email',
        action='confirm',
        token=token,
        _external=True)
    html = render_template('email/activate.html',
            confirm_url = confirm_url)

    msg = Message(subject=subject, html=html, recipients=[email])
    mail.send(msg)

def send_reset_password_mail(email):
    subject = 'Reset your password'
    token = ts.dumps(email, salt='password-reset-key')

    reset_url = url_for(
        'home.reset_password',
        token=token,
        _external=True)
    html = render_template('email/reset-password.html',
            reset_url = reset_url)

    msg = Message(subject=subject, html=html, recipients=[email])
    mail.send(msg)



def allowed_file(filename,type):
    return '.' in filename and \
            filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS'][type]

def sanitize(text):
    if text.strip():
        cleaner = Cleaner(safe_attrs_only=False, style=True)
        return cleaner.clean_html(text)
    else:
        return text

@app.template_filter('abstract')
def html_abstract(text):
    return Markup(text).striptags()[0:150]

@app.template_filter('time_interval')
def time_interval(seconds):
    minutes = int(seconds / 60)
    hours = int(minutes / 60)
    text = str(hours)
    text += ':' + str(int((minutes % 60) / 10)) + str((minutes % 60) % 10)
    if seconds % 60 != 0:
        text += ':' + str(int((seconds % 60) / 10)) + str((seconds % 60) % 10)
    return text

@app.template_filter('localtime')
def localtime_minute(date):
    #local = pytz.utc.localize(date, is_dst=False).astimezone(pytz.timezone('Asia/Shanghai'))
    local = date
    try:
        return local.strftime('%Y-%m-%d %H:%M')
    except:
        return 'N/A'

@app.template_filter('updatetime')
def updatetime_minute(date):
    #local = pytz.utc.localize(date, is_dst=False).astimezone(pytz.timezone('Asia/Shanghai'))
    local = date
    try:
        now = datetime.now()
        if (now.date() - local.date()).days == 0:
            return local.strftime('今天 %H:%M')
        elif (now.date() - local.date()).days == 1:
            return local.strftime('昨天 %H:%M')
        elif now.year == local.year:
            return str(local.month) + '月' + str(local.day) + '日 ' + local.strftime('%H:%M')
        else:
            return str(local.year) + '年' + str(local.month) + '月' + str(local.day) + '日 ' + local.strftime('%H:%M')
    except:
        return 'N/A'

_word_split_re = re.compile(r'''([<>\s]+)''')
_punctuation_re = re.compile(
    '^(?P<lead>(?:%s)*)(?P<middle>.*?)(?P<trail>(?:%s)*)$' % (
        '|'.join(map(re.escape, ('(', '<', '&lt;'))),
        '|'.join(map(re.escape, ('.', ',', ')', '>', '\n', '&gt;')))
    )
)
_simple_email_re = re.compile(r'^\S+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+$')
_striptags_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
_entity_re = re.compile(r'&([^;]+);')
_letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_digits = '0123456789'

@app.template_filter('my_urlize')
def my_urlize(text, trim_url_limit=None, nofollow=False, target=None):
    """Converts any URLs in text into clickable links. Works on http://,
    https:// and www. links. Links can have trailing punctuation (periods,
    commas, close-parens) and leading punctuation (opening parens) and
    it'll still do the right thing.
    If trim_url_limit is not None, the URLs in link text will be limited
    to trim_url_limit characters.
    If nofollow is True, the URLs in link text will get a rel="nofollow"
    attribute.
    If target is not None, a target attribute will be added to the link.
    """
    trim_url = lambda x, limit=trim_url_limit: limit is not None \
                         and (x[:limit] + (len(x) >=limit and '...'
                         or '')) or x
    words = _word_split_re.split(text)
    nofollow_attr = nofollow and ' rel="nofollow"' or ''
    if target is not None and isinstance(target, string_types):
        target_attr = ' target="%s"' % escape(target)
    else:
        target_attr = ''
    for i, word in enumerate(words):
        match = _punctuation_re.match(word)
        if match:
            lead, middle, trail = match.groups()
            if middle.startswith('www.') or (
                '@' not in middle and
                not middle.startswith('http://') and
                not middle.startswith('https://') and
                len(middle) > 0 and
                middle[0] in _letters + _digits and (
                    middle.endswith('.org') or
                    middle.endswith('.net') or
                    middle.endswith('.com')
                )):
                middle = '<a href="http://%s"%s%s>%s</a>' % (middle,
                    nofollow_attr, target_attr, trim_url(middle))
            if middle.startswith('http://') or \
               middle.startswith('https://'):
                middle = '<a href="%s"%s%s>%s</a>' % (middle,
                    nofollow_attr, target_attr, trim_url(middle))
            if '@' in middle and not middle.startswith('www.') and \
               not ':' in middle and _simple_email_re.match(middle):
                middle = '<a href="mailto:%s">%s</a>' % (middle, middle)
            if lead + middle + trail != word:
                words[i] = lead + middle + trail
    return u''.join(words)

RESERVED_USERNAME = set(['管理员', 'admin', 'root',
    'Administrator', 'example', 'test'])

def validate_username(username, check_db=True):
    if re.search('[@&<>"\'\s]', username):
        return ('此用户名含有非法字符，不能注册！')
    if username in RESERVED_USERNAME:
        return ('此用户名已被保留，不能注册！')
    if check_db and User.query.filter_by(username=username).first():
        return ('此用户名已被他人使用！')
    return 'OK'

def validate_email(email):
    regex = re.compile("[a-zA-Z0-9_]+@(mail\.)?ustc\.edu\.cn")
    if not regex.fullmatch(email):
        return ('必须使用科大邮箱注册!')
    if User.query.filter_by(email=email).first():
        return ('此邮件地址已被注册！')
    return 'OK'


# HTTP basic auth login

def check_auth(username, password):
    return username == app.config['WEB_AUTH_USER'] and password == app.config['WEB_AUTH_PASSWORD']

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
