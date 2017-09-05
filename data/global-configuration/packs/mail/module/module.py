import time
import os
import traceback
import smtplib
import datetime

try:
    import jinja2
except ImportError:
    jinja2 = None

from opsbro.module import HandlerModule



class MailHandlerModule(HandlerModule):
    implement = 'mail'
    
    parameters = {
        # 'enabled': BoolParameter(default=False),
        # 'port'   : IntParameter(default=53),
        # 'domain' : StringParameter(default=''),
    }
    
    
    def __init__(self):
        super(MailHandlerModule, self).__init__()
    
    
    def send_mail(self, handler, check):
        
        addr_from = handler.get('addr_from', 'opsbro@mydomain.com')
        smtp_server = handler.get("smtp_server", "localhost")
        smtps = handler.get("smtps", False)
        contacts = handler.get('contacts', ['admin@mydomain.com'])
        subject_p = handler.get('subject_template', 'mail.subject.tpl')
        text_p = handler.get('text_template', 'mail.text.tpl')
        templates_dir = os.path.join(handler.get('configuration_dir', ''), 'templates')
        
        # go connect now
        try:
            self.logger.debug("Handler: MAIL connection to %s" % smtp_server)
            s = smtplib.SMTP(smtp_server, timeout=30)
            
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            
            subject_f = os.path.join(templates_dir, subject_p)
            text_f = os.path.join(templates_dir, text_p)
            
            if not os.path.exists(subject_f):
                self.logger.error('Missing template file %s' % subject_f)
                return
            if not os.path.exists(text_f):
                self.logger.error('Missing template file %s' % text_f)
                return
            with open(subject_f) as f:
                subject_buf = f.read()
            with open(text_f) as f:
                text_buf = f.read()
            
            subject_tpl = jinja2.Template(subject_buf)
            subject_m = subject_tpl.render(handler=handler, check=check, _time=_time)
            text_tpl = jinja2.Template(text_buf)
            text_m = text_tpl.render(handler=handler, check=check, _time=_time)
            
            msg = '''\
    From: %s
    Subject: %s

    %s

    ''' % (addr_from, subject_m, text_m)
            # % (addr_from, check['name'], check['state'], _time, check['output'])
            self.logger.debug("Sending mail from:%s to %s. Message=%s" % (addr_from, contacts, msg))
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            self.logger.error('Cannot send mail: %s' % traceback.format_exc())
    
    
    def handle(self, handler, obj, event):
        self.logger.info('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.send_mail(handler, obj)
