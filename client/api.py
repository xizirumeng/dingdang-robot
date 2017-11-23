# -*- coding: utf-8-*-
import logging
import hashlib
from bottle import route, run, template, request, error
def api_service(mic, brain, user, password, port):
    logger = logging.getLogger(__name__)
    @route('/dingdang/<name>', method = 'GET')
    def index(name):
        u = request.forms.get("u")
        p = request.forms.get("p")
        print p, password
        print u, user
        print hashlib.md5(p), hashlib.md5(password)
        if user != u or hashlib.md5(p) != hashlib.md5(password):
            return template('Incorrect username or password !', name=name)
        command = request.forms.get('command')
        if command.find('[control]'):
            # 执行叮当命令
            brain.query([command.replace('[control]', '').strip()])
        elif command.find('[echo]'):
            mic.say(command.replace('[echo]', '').strip())
        elif command.find('[shell]'):
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