from flask import Blueprint,request, redirect,url_for,render_template,flash, abort, jsonify, Response
from flask_login import login_user, login_required, current_user, logout_user
from app.models import Task, SyncRecord, ErrorLog, DevUpdate
from app.utils import ts, send_confirm_mail, send_reset_password_mail, QueryDataLogHistory, QueryDataLogAnomaly
from flask_babel import gettext as _
from datetime import datetime
from sqlalchemy import union, or_
from sqlalchemy.sql.expression import literal_column, text
from app import db
from app import app
from flask import send_from_directory
import os
import signal
import datetime
import csv
import io

home = Blueprint('home',__name__)

@home.route('/')
def index():
    all_tasks = Task.query.order_by(Task.name).all()
    running_tasks = Task.query.filter(Task.sync_is_in_progress == True).all()
    task_records = Task.query.join(SyncRecord, Task.last_sync_record_id == SyncRecord.id)
    success_tasks = task_records.filter(SyncRecord.status == 1).all()
    warning_tasks = task_records.filter(SyncRecord.status == 2).all()
    error_tasks = task_records.filter(SyncRecord.status == 3).all()
    latest_tasks = task_records.order_by(SyncRecord.begin_time.desc()).all()
    dev_updates = DevUpdate.query.order_by(DevUpdate.time.desc()).all()
    return render_template('index.html', all_tasks=all_tasks, running_tasks=running_tasks, success_tasks=success_tasks, warning_tasks=warning_tasks, error_tasks=error_tasks, latest_tasks=latest_tasks, dev_updates=dev_updates)

@home.route('/history/<int:date>')
def history(date):
    if date == 0:
        title = '今日任务'
        history_records = SyncRecord.query.filter(SyncRecord.end_time >= datetime.date.today())
    elif date == 1:
        title = '昨日任务'
        history_records = SyncRecord.query.filter(SyncRecord.end_time >= datetime.date.today() - datetime.timedelta(days=1)).filter(SyncRecord.begin_time < datetime.date.today())
    elif date == 2:
        title = '历史任务'
        history_records = SyncRecord.query.filter(SyncRecord.begin_time < datetime.date.today() - datetime.timedelta(days=1))
    else:
        abort(404)
    ordered = history_records.order_by(SyncRecord.end_time.desc()).all()
    all_tasks = Task.query.order_by(Task.name).all()
    return render_template('history.html', title=title, history_records=ordered, all_tasks=all_tasks)

@home.route('/export/<int:export_type>/<string:records>')
def export_records(export_type, records):
    record_ids = map(int, records.split(','))
    si = io.StringIO()
    cw = csv.writer(si)
    header = []
    if export_type == 1:
        header = ['任务名称', '数据表名', '采集周期（小时）']
    elif export_type == 2:
        header = ['任务名称', '采集批次号', '状态', '开始时间', '结束时间', '采集网页数', '采集数据总量', '新增数据量', '更新数据量', '异常数据量']
    elif export_type == 3:
        header = ['任务名称', '采集批次号', '采集时间', '数据状态', '数据表名', '数据ID', '数据内容', '数据源URL', '原始网页内容']
    elif export_type == 4:
        header = ['任务名称', '采集批次号', '采集时间', '数据表名', '数据ID', '异常类型', '异常字段名', '异常内容', '备注']
    cw.writerow(header)

    for record_id in record_ids:
        record = SyncRecord.query.filter(SyncRecord.id == record_id).first()
        if not record:
            continue
        if export_type == 1:
            cw.writerow([record.task.name, record.task.resource_table, int(record.task.sync_frequency / 3600)])
        elif export_type == 2:
            record_status_map = ['运行中', '已完成', '异常终止', '失败']
            cw.writerow([
                record.task.name, 
                record.batch_no,
                record_status_map[record.status],
                record.begin_time,
                record.end_time,
                record.crawled_webpages,
                record.total_records,
                record.new_records,
                record.updated_records,
                record.error_count
                ])
        elif export_type == 3:
            QueryDataLogHistory(cw, record.task.name, record.task.resource_table, record.batch_no)
        elif export_type == 4:
            QueryDataLogAnomaly(cw, record.task.name, record.task.resource_table, record.batch_no)

    csv_str = si.getvalue().strip('\r\n')
    time = datetime.datetime.now().strftime('%Y.%m.%d_%H.%M.%S')
    return Response(csv_str, mimetype="text/csv",
                    headers={"Content-disposition": "attachment; filename=DataLog_" + time + ".csv"})


@home.route('/task/<string:name>')
def task(name):
    if not name:
   	    abort(400)
    task = Task.query.filter(Task.name == name).first()
    if not task:
   	    abort(404)
    all_tasks = Task.query.order_by(Task.name).all()
    return render_template('task.html', task=task, all_tasks=all_tasks)

@home.route('/task/<string:name>/stop')
def stop_task(name):
    if not name:
   	    abort(400)
    task = Task.query.filter(Task.name == name).first()
    if not task:
   	    abort(404)
    if not task.sync_is_in_progress:
        abort(403)

    task.sync_is_in_progress = False

    try:
        os.kill(task.sync_process_id, signal.SIGKILL)
    except Exception as e:
        print(e)
    task.last_sync_record.status = 2 # error exit
    task.last_sync_record.end_time = datetime.now()
    task.save()

    return redirect(url_for('home.task', name=name))

@home.route('/task/<string:name>/start')
def start_task(name):
    if not name:
   	    abort(400)
    task = Task.query.filter(Task.name == name).first()
    if not task:
   	    abort(404)
    # stop existing task before forkng new
    if task.sync_is_in_progress:
        stop_task(name)

    record = SyncRecord()
    record.task = task
    record.begin_time = datetime.now()
    record.status = 0

    record.crawled_webpages = 0
    record.total_records = 0
    record.new_records = 0
    record.updated_records = 0
    record.saved_images = 0
    record.error_count = 0

    record.save()

    import subprocess
    child_process = subprocess.Popen(["/root/scrapywrapper/RunSpider.sh", task.name])
    if not child_process:
        record.status = 3
        record.end_time = datetime.now()
        record.error_count = 1
        record.save()

        task.sync_is_in_progress = False
        task.last_sync_record = record
        task.save()

        abort(502)
        return

    task.sync_is_in_progress = True
    task.last_sync_record = record
    task.sync_process_id = child_process.pid
    task.save()
    return redirect(url_for('home.task', name=name))


@home.route('/task/<string:name>/update_status', methods=['GET', 'POST'])
@app.csrf.exempt
def task_update_sync_status(name):
    if not name:
   	    abort(400)
    task = Task.query.filter(Task.name == name).first()
    if not task:
   	    abort(404)
    record = task.last_sync_record
    if not record:
        abort(403)

    record.status = request.values.get('status')
    record.crawled_webpages = request.values.get('crawled_webpages')
    record.total_records = request.values.get('total_records')
    record.new_records = request.values.get('new_records')
    record.updated_records = request.values.get('updated_records')
    record.saved_images = request.values.get('saved_images')
    record.error_count = request.values.get('error_count')
    record.end_time = datetime.now()
    record.save()

    if int(record.status) != 0:
        task.sync_is_in_progress = False
        task.save()
    return 'OK'


@home.route('/task/<string:name>/log_error', methods=['GET', 'POST'])
@app.csrf.exempt
def task_log_error(name):
    if not name:
   	    abort(400)
    task = Task.query.filter(Task.name == name).first()
    if not task:
   	    abort(404)

    # TODO

    return redirect(url_for('home.task', name=name))

@home.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@home.route('/task/new', methods=['POST'])
@app.csrf.exempt
def new_task():
    name = request.values.get('name')
    sync_frequency = request.values.get('freq')
    sync_time = request.values.get('time')
    incremental = request.values.get('incremental')
    try:
        sync_time = int(sync_time)
    except:
        ts = sync_time.split(":")
        sync_time = 0
        for t in range(0,3):
            try:
                sync_time *= 60
                sync_time += int(ts[t])
            except:
                pass

    incremental = 1 if incremental else 0

    task = Task.query.filter(Task.name == name).first()
    if not task:
        task = Task()
    task.name = name
    task.sync_frequency = sync_frequency
    task.sync_time = sync_time
    task.incremental_sync = incremental
    task.save()
    return redirect(url_for('home.task', name=name))

@home.route('/dev_update/new', methods=['POST'])
@app.csrf.exempt
def new_dev_update():
    task_name = request.values.get('task')
    task = Task.query.filter(Task.name == task_name).first()
    if not task:
        abort(404)
    update = DevUpdate()
    update.task = task
    update.title = request.values.get('title')
    update.time = datetime.now()
    update.content = request.values.get('content')
    update.save()
    return redirect(url_for('home.index'))

