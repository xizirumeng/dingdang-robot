# -*- coding: utf-8-*-
import logging
import hashlib
import subprocess
from bottle import route, run, request, error
def api_service(mic, brain, user, password, port):
    logger = logging.getLogger(__name__)
    @route('/dingdang/api', method = 'POST')
    def index():
        u = request.POST.get("u")
        p = request.POST.get("p")
        html = request.POST.get("html")
        if user != u or hashlib.md5(p).hexdigest() != hashlib.md5(password).hexdigest():
            return '{"msg":"Incorrect username or password","success":false}'
        command = request.POST.get("command")
        if '[control]' in command:
            # 执行命令
            brain.query([command.replace('[control]','').strip()])
            return '{"msg":"success","success":true}'
        elif '[echo]' in command:
            # 说话
            mic.say([command.replace('[echo]','').strip()])
            return '{"msg":"success","success":true}'
        elif '[shell]' in command:
            p = subprocess.Popen(command.replace('[shell]','').strip(), shell = True, stdout = subprocess.PIPE)
            out, err = p.communicate()
            for line in out.splitlines():
                return '{"msg":"success","success":true,"data":"'+ (html %line) +'"}'
        return '{"msg":"success","success":true}'

    @error(403)
    def mistake403(code):
        return '{"msg":"The parameter you passed has the wrong format!","success":false}'

    @error(404)
    def mistake404(code):
        return '{"msg":"Sorry, this page does not exist!","success":false}'
    try:
        run(host='0.0.0.0', port=port)
    except Exception, e:
        logger.error(e)
