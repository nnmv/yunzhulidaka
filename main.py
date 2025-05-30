from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json
import logging
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    cookie = db.Column(db.Text, nullable=False)
    morning_time = db.Column(db.String(20), nullable=False)
    afternoon_time = db.Column(db.String(20), nullable=False)
    evening_time = db.Column(db.String(20), nullable=False)
    pushplus_token = db.Column(db.String(100), nullable=False)

# 定义打卡记录模型
class ClockRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    clock_type = db.Column(db.String(20), nullable=False)  # morning, afternoon, evening
    clock_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Boolean, nullable=False)  # True for success, False for failure
    message = db.Column(db.Text)
    
    user = db.relationship('User', backref=db.backref('records', lazy=True))

# 初始化数据库
with app.app_context():
    db.create_all()

# PushPlus推送函数
def push_notification(token, title, content):
    url = "https://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        result = response.json()
        if result.get("code") == 200:
            logger.info("PushPlus推送成功")
            return True
        else:
            logger.error(f"PushPlus推送失败: {result.get('msg')}")
            return False
    except Exception as e:
        logger.error(f"PushPlus推送异常: {str(e)}")
        return False

# 打卡函数
def clock_in(user_id, clock_type):
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            logger.error(f"用户ID {user_id} 不存在")
            return
        
        # 获取当前日期
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 确定打卡时间
        if clock_type == "morning":
            clock_time = user.morning_time
            sign_stat = 2  # 早上打卡状态码
        elif clock_type == "afternoon":
            clock_time = user.afternoon_time
            sign_stat = 4  # 中午/下午打卡状态码
        elif clock_type == "evening":
            clock_time = user.evening_time
            sign_stat = 16  # 晚上打卡状态码
        else:
            logger.error(f"未知的打卡类型: {clock_type}")
            return
        
        # 构建请求
        url = "https://webapp.yzl.e-chinalife.com/kaoqin/_ReportData/ckaoqin_sign?dataset=sign_ds"
        headers = {
            "Host": "webapp.yzl.e-chinalife.com",
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://webapp.yzl.e-chinalife.com",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 BrowseMode/Mobile iPhoneModel/iPhone15,3 SystemVersion/16.2; YunZhuLi/5.2.2-rc1.idc_ym.idc_st.prt_hy",
            "Connection": "keep-alive",
            "Referer": "https://webapp.yzl.e-chinalife.com/kaoqin/ckaoqin/index.jsp",
            "Cookie": user.cookie
        }
        
        # 请求体数据
        data = {
            "sign_address": "河南省开封市河南省开封市顺河回族区公园路辅路公园路38号",
            "sign_longitude": "114.37985109081457",
            "sign_latitude": "34.79596700463172",
            "deviceid": "i1_7a667f19e84ffc16fafa55d840cf62f1",
            "sign_stat": sign_stat,
            "banci_name": "开封",
            "sd1sbtime": "08:30",
            "sd1xbtime": "12:00",
            "sd2sbtime": "14:00",
            "sd2xbtime": "17:30",
            "kaoqin_times": kaoqin_times
        }
        
        try:
            # 发送打卡请求
            response = requests.post(url, headers=headers, data=data)
            response_text = response.text
            
            # 判断打卡结果
            if "执行成功" in response_text:
                result = True
                message = "打卡成功"
                # 推送成功通知
                push_title = "打卡成功通知"
                push_content = f"{user.username}，您已完成打卡，打卡时间为：{clock_time}"
                push_notification(user.pushplus_token, push_title, push_content)
            else:
                result = False
                message = "打卡失败，可能Cookie过期"
                # 推送失败通知
                push_title = "打卡失败通知"
                push_content = f"{user.username}，打卡失败，可能未Cookie过期，失败时间为：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                push_notification(user.pushplus_token, push_title, push_content)
            
            # 记录打卡结果
            record = ClockRecord(
                user_id=user_id,
                clock_type=clock_type,
                clock_time=datetime.now(),
                status=result,
                message=message
            )
            db.session.add(record)
            db.session.commit()
            
            logger.info(f"用户 {user.username} {clock_type} 打卡{'成功' if result else '失败'}")
            
        except Exception as e:
            logger.error(f"打卡异常: {str(e)}")
            # 记录异常
            record = ClockRecord(
                user_id=user_id,
                clock_type=clock_type,
                clock_time=datetime.now(),
                status=False,
                message=f"打卡异常: {str(e)}"
            )
            db.session.add(record)
            db.session.commit()
            
            # 推送异常通知
            push_title = "打卡异常通知"
            push_content = f"{user.username}，打卡过程中出现异常，异常信息为：{str(e)}"
            push_notification(user.pushplus_token, push_title, push_content)

# 添加任务到调度器
def add_jobs_to_scheduler(scheduler):
    with app.app_context():
        users = User.query.all()
        for user in users:
            # 早上打卡任务 (周一到周五)
            hour, minute = map(int, user.morning_time.split(':'))
            scheduler.add_job(
                func=clock_in,
                args=[user.id, "morning"],
                trigger='cron',
                hour=hour,
                minute=minute,
                day_of_week='mon-fri',
                id=f'morning_{user.id}'
            )
            
            # 中午打卡任务 (周一到周五)
            hour, minute = map(int, user.afternoon_time.split(':'))
            scheduler.add_job(
                func=clock_in,
                args=[user.id, "afternoon"],
                trigger='cron',
                hour=hour,
                minute=minute,
                day_of_week='mon-fri',
                id=f'afternoon_{user.id}'
            )
            
            # 晚上打卡任务 (周一到周五)
            hour, minute = map(int, user.evening_time.split(':'))
            scheduler.add_job(
                func=clock_in,
                args=[user.id, "evening"],
                trigger='cron',
                hour=hour,
                minute=minute,
                day_of_week='mon-fri',
                id=f'evening_{user.id}'
            )

# 初始化调度器
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
add_jobs_to_scheduler(scheduler)

# 前端页面路由
@app.route('/')
def index():
    return render_template('index.html')

# 管理页面路由 (需要密码保护)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        # 检查密码 (实际使用中应使用更安全的密码存储方式)
        if password == 'your_admin_password':  # 请修改为实际密码
            users = User.query.all()
            return render_template('admin.html', users=users)
        else:
            return "密码错误"
    return render_template('login.html')

# 打卡记录页面
@app.route('/admin/records/<int:user_id>')
def user_records(user_id):
    try:
        user = User.query.get_or_404(user_id)
        records = ClockRecord.query.filter_by(user_id=user_id).order_by(ClockRecord.clock_time.desc()).all()
        return render_template('records.html', user=user, records=records)
    except Exception as e:
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

# API路由
@app.route('/api/test_push', methods=['POST'])
def test_push():
    data = request.json
    username = data.get('username')
    morning_time = data.get('morning_time')
    afternoon_time = data.get('afternoon_time')
    evening_time = data.get('evening_time')
    pushplus_token = data.get('pushplus_token')
    
    title = "测试推送"
    content = f"{username}，打卡时间分别为：<br>早上：{morning_time}<br>中午：{afternoon_time}<br>晚上：{evening_time}"
    
    success = push_notification(pushplus_token, title, content)
    return jsonify({"success": success})

@app.route('/api/save_user', methods=['POST'])
def save_user():
    data = request.json
    username = data.get('username')
    cookie = data.get('cookie')
    morning_time = data.get('morning_time')
    afternoon_time = data.get('afternoon_time')
    evening_time = data.get('evening_time')
    pushplus_token = data.get('pushplus_token')
    
    try:
        # 检查是否已存在该用户
        user = User.query.filter_by(username=username).first()
        if user:
            # 更新用户信息
            user.cookie = cookie
            user.morning_time = morning_time
            user.afternoon_time = afternoon_time
            user.evening_time = evening_time
            user.pushplus_token = pushplus_token
        else:
            # 创建新用户
            user = User(
                username=username,
                cookie=cookie,
                morning_time=morning_time,
                afternoon_time=afternoon_time,
                evening_time=evening_time,
                pushplus_token=pushplus_token
            )
            db.session.add(user)
        
        db.session.commit()
        
        # 更新调度器中的任务
        scheduler.remove_all_jobs()
        add_jobs_to_scheduler(scheduler)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/update_user', methods=['POST'])
def update_user():
    data = request.json
    user_id = data.get('id')
    username = data.get('username')
    cookie = data.get('cookie')
    morning_time = data.get('morning_time')
    afternoon_time = data.get('afternoon_time')
    evening_time = data.get('evening_time')
    pushplus_token = data.get('pushplus_token')
    
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"success": False, "message": "用户不存在"})
        
        user.username = username
        user.cookie = cookie
        user.morning_time = morning_time
        user.afternoon_time = afternoon_time
        user.evening_time = evening_time
        user.pushplus_token = pushplus_token
        
        db.session.commit()
        
        # 更新调度器中的任务
        scheduler.remove_all_jobs()
        add_jobs_to_scheduler(scheduler)
        
        return jsonify({"success": True, "message": "更新成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    user_id = request.json.get('id')
    
    try:
        # 先删除用户的打卡记录
        ClockRecord.query.filter_by(user_id=user_id).delete()
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"success": False, "message": "用户不存在"})
        
        db.session.delete(user)
        db.session.commit()
        
        # 更新调度器中的任务
        scheduler.remove_all_jobs()
        add_jobs_to_scheduler(scheduler)
        
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)    