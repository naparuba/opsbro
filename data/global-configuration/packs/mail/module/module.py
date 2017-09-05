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
from opsbro.parameters import BoolParameter, StringParameter, StringListParameter


class MailHandlerModule(HandlerModule):
    implement = 'mail'
    
    parameters = {
        'enabled'               : BoolParameter(default=False),
        'severities'            : StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'contacts'              : StringListParameter(default=['admin@mydomain.com']),
        'addr_from'             : StringParameter(default='opsbro@mydomain.com'),
        'smtp_server'           : StringParameter(default='localhost'),
        'smtps'                 : BoolParameter(default=False),
        'check_subject_template': StringParameter(default='mail-check-subject.tpl'),
        'check_text_template'   : StringParameter(default='mail-check-text.tpl'),
    }
    
    
    def __init__(self):
        super(MailHandlerModule, self).__init__()
    
    
    def send_mail(self, handler, check):
        
        addr_from = self.get_parameter('addr_from')
        smtp_server = self.get_parameter("smtp_server")
        smtps = self.get_parameter("smtps")
        contacts = self.get_parameter('contacts')
        subject_p = self.get_parameter('check_subject_template')
        text_p = self.get_parameter('check_text_template')
        templates_dir = os.path.join(self.pack_directory, 'templates')
        
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
        enabled = self.get_parameter('enabled')
        if not enabled:
            self.logger.debug('Mail module is not enabled, skipping check alert sent')
            return
        
        self.logger.info('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.send_mail(handler, obj)
