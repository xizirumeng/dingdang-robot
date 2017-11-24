# -*- coding: utf-8-*-
import logging
import hashlib
import thread
from bottle import route, run, template, request, error
def api_service(mic, brain, user, password, port):
    logger = logging.getLogger(__name__)
    @route('/dingdang/<name>', method = 'GET')
    def index(name):
        u = request.query.u
        p = request.query.p
        if user != u or hashlib.md5(p).hexdigest() != hashlib.md5(password).hexdigest():
            return template('Incorrect username or password !', name=name)
        command = request.query.command
        print command
        if command.find('[control]'):
            thread.start_new_thread(control, command)
        elif command.find('[echo]'):
            thread.start_new_thread(echo, command)
        elif command.find('[shell]'):
            mic.say(command.replace('[echo]', '').strip())

        return template('<b>Hello {{name}}</b>!', name=name)

    @error(403)
    def mistake403(code):
        return 'The parameter you passed has the wrong format!'

    @error(404)
    def mistake404(code):
        return 'Sorry, this page does not exist!'

    def control(command):
        # 执行叮当命令
        brain.query([command.replace('[control]', '').strip()])
    def echo(command):
        # 执行叮当命令
        mic.say([command.replace('[echo]', '').strip()])
    try:
        run(host='0.0.0.0', port=port)
    except Exception, e:
        logger.error(e)