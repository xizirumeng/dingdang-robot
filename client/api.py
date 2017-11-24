# -*- coding: utf-8-*-
import logging
import hashlib
import thread
from bottle import route, run, template, request, error
def api_service(mic, brain, user, password, port):
    logger = logging.getLogger(__name__)
    @route('/dingdang/', method = 'GET')
    def index():
        u = request.query.u
        p = request.query.p
        if user != u or hashlib.md5(p).hexdigest() != hashlib.md5(password).hexdigest():
            return template('Incorrect username or password !', name=name)
        command = request.query.command
        if '[control]' in command:
            # 执行命令
            brain.query([command.replace('[control]','').strip()])
            return '拍照成功！'
        elif '[echo]' in command:
            # 说话
            mic.say([command.replace('[echo]','').strip()])
            return 'true'
        elif '[shell]' in command:
            mic.say(command.replace('[echo]', '').strip())

        return template('<b>Hello {{name}}</b>!', name=name)

    @error(403)
    def mistake403(code):
        return 'The parameter you passed has the wrong format!'

    @error(404)
    def mistake404(code):
        return 'Sorry, this page does not exist!'
    try:
        run(host='0.0.0.0', port=port)
    except Exception, e:
        logger.error(e)
