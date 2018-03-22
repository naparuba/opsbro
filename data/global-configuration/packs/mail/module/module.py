import time
import os
import traceback
import datetime

from opsbro.library import libstore
from opsbro.module import HandlerModule
from opsbro.parameters import BoolParameter, StringParameter, StringListParameter


class MailHandlerModule(HandlerModule):
    implement = 'mail'
    
    parameters = {
        'enabled'               : BoolParameter(default=False),
        'severities'            : StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'contacts'              : StringListParameter(default=['naparuba@gmail.com']),
        'addr_from'             : StringParameter(default='opsbro@mydomain.com'),
        'smtp_server'           : StringParameter(default='localhost'),
        'smtps'                 : BoolParameter(default=False),
        'check_subject_template': StringParameter(default='mail-check-subject.tpl'),
        'check_text_template'   : StringParameter(default='mail-check-text.tpl'),
        
        'group_subject_template': StringParameter(default='mail-group-subject.tpl'),
        'group_text_template'   : StringParameter(default='mail-group-text.tpl'),
        
    }
    
    
    def __init__(self):
        super(MailHandlerModule, self).__init__()
        self.jinja2 = libstore.get_jinja2()
    
    
    def send_mail_check(self, check):
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
            # Lazy load smtplib
            import smtplib
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
                subject_buf = f.read().decode('utf8', 'ignore')
            with open(text_f) as f:
                text_buf = f.read().decode('utf8', 'ignore')
            
            subject_tpl = self.jinja2.Template(subject_buf)
            subject_m = subject_tpl.render(check=check, _time=_time)
            text_tpl = self.jinja2.Template(text_buf)
            text_m = text_tpl.render(check=check, _time=_time)
            
            msg = '''From: %s
Subject: %s

%s

''' % (addr_from, subject_m, text_m)
            # % (addr_from, check['name'], check['state'], _time, check['output'])
            self.logger.debug("Sending mail from:%s to %s. Message=%s" % (addr_from, contacts, msg))
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            self.logger.error('Cannot send mail: %s' % traceback.format_exc())
    
    
    def send_mail_group(self, group, group_modification):
        addr_from = self.get_parameter('addr_from')
        smtp_server = self.get_parameter("smtp_server")
        smtps = self.get_parameter("smtps")
        contacts = self.get_parameter('contacts')
        subject_p = self.get_parameter('group_subject_template')
        text_p = self.get_parameter('group_text_template')
        templates_dir = os.path.join(self.pack_directory, 'templates')
        
        # go connect now
        try:
            self.logger.debug("Handler: MAIL connection to %s" % smtp_server)
            # Lazy load smtplib
            import smtplib
            s = smtplib.SMTP(smtp_server, timeout=30)
            
            subject_f = os.path.join(templates_dir, subject_p)
            text_f = os.path.join(templates_dir, text_p)
            
            if not os.path.exists(subject_f):
                self.logger.error('Missing template file %s' % subject_f)
                return
            if not os.path.exists(text_f):
                self.logger.error('Missing template file %s' % text_f)
                return
            with open(subject_f) as f:
                subject_buf = f.read().decode('utf8', 'ignore')
            with open(text_f) as f:
                text_buf = f.read().decode('utf8', 'ignore')
            
            subject_tpl = self.jinja2.Template(subject_buf)
            subject_m = subject_tpl.render(group=group, group_modification=group_modification)
            text_tpl = self.jinja2.Template(text_buf)
            text_m = text_tpl.render(group=group, group_modification=group_modification)
            
            msg = '''From: %s
Subject: %s

%s

''' % (addr_from, subject_m, text_m)
            self.logger.debug("Sending mail from:%s to %s. Message=%s" % (addr_from, contacts, msg))
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            self.logger.error('Cannot send mail: %s' % traceback.format_exc())
    
    
    def handle(self, obj, event):
        enabled = self.get_parameter('enabled')
        if not enabled:
            self.logger.debug('Mail module is not enabled, skipping check alert sent')
            return
        
        self.logger.debug('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.send_mail_check(obj)
        
        if evt_type == 'group_change':
            evt_data = event['evt_data']
            group_modification = evt_data['modification']
            self.send_mail_group(obj, group_modification)
