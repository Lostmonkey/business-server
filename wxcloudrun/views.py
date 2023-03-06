import logging

from datetime import datetime
from flask import render_template, request
from run import app
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid
from wxcloudrun.model import Counters
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response
import uuid
import json
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('log')
logging.basicConfig(level=logging.DEBUG)


VolcAuth = "cNA03Z6qXenOhzDkGpc93PZETDZvoWAC"

wxAppId = "wx022394022eafe29b"
wxSecret = "025560721342e9401bccd561f1f2676f"

GptResult = {}


@app.route('/')
def index():
    """
    :return: 返回index页面
    """
    return render_template('index.html')


@app.route('/api/count', methods=['POST'])
def count():
    """
    :return:计数结果/清除结果
    """

    # 获取请求体参数
    params = request.get_json()

    # 检查action参数
    if 'action' not in params:
        return make_err_response('缺少action参数')

    # 按照不同的action的值，进行不同的操作
    action = params['action']

    # 执行自增操作
    if action == 'inc':
        counter = query_counterbyid(1)
        if counter is None:
            counter = Counters()
            counter.id = 1
            counter.count = 1
            counter.created_at = datetime.now()
            counter.updated_at = datetime.now()
            insert_counter(counter)
        else:
            counter.id = 1
            counter.count += 1
            counter.updated_at = datetime.now()
            update_counterbyid(counter)
        return make_succ_response(counter.count)

    # 执行清0操作
    elif action == 'clear':
        delete_counterbyid(1)
        return make_succ_empty_response()

    # action参数错误
    else:
        return make_err_response('action参数错误')


@app.route('/api/count', methods=['GET'])
def get_count():
    """
    :return: 计数的值
    """
    counter = Counters.query.filter(Counters.id == 1).first()
    return make_succ_response(0) if counter is None else make_succ_response(counter.count)


@app.route("/api/volc/token")
def get_token():
    ret = {
        "auth": VolcAuth,
        "req_id": uuid.uuid4().hex
    }
    return json.dumps(ret)


@app.route("/api/wechat/openid")
def get_openid():
    logger.info(request.headers)
    ret = {
        "openid": request.headers["X-WX-OPENID"],
    }
    return json.dumps(ret)


executor = ThreadPoolExecutor(2)


def submit_answer_2_gpt(req_id, param):
    ret = requests.get("http://120.79.242.200:5088/teacher", json=param, timeout=30000)
    GptResult[req_id] = ret.text


@app.route("/api/chatgpt/answer", methods=["POST"])
def submit_answer():
    sys = "You are a professional TOEFL speaking test examiner. Please rate my answer according to official TOEFL Speaking rubrics, and give me a Totol score as well as a  breakdown chart of my speaking score.Please also give me the detailed analysis why I got the above score.  The analysis should include mistakes that I have made in my response as well as places that I could have paid more attention to or improve.Please in the end give me a sample response of the topic. This sample response should be carefully structured with detailed examples and meet the official TOEFL speaking rubrics with exam full marks."
    req_id = request.json["req_id"]
    ques = request.json["question"]
    ans = request.json["answer"]

    param = {
        "req_id": req_id,
        "system": sys,
        "user": "The Question is: \"" + ques + "\", the student's answer is: \"" + ans + "\""
    }

    print(json.dumps(param))

    GptResult.pop(req_id, None)

    executor.submit(submit_answer_2_gpt, req_id, param)

    return json.dumps(param)


@app.route("/api/chatgpt/eval", methods=["GET"])
def get_eval():
    req_id = request.args["req_id"]

    if req_id in GptResult:
        return json.dumps({"status": 0, "data": GptResult[req_id]})
    else:
        return json.dumps({"status": 1000, "data": ""})
