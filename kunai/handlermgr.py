import os
import traceback
import smtplib
import datetime
import time

try:
    import jinja2
except ImportError:
    jinja2 = None

from kunai.log import logger


# TODO: finish the email part

class HandlerManager(object):
    def __init__(self):
        self.handlers = {}
    
    
    def send_mail(self, handler, check):
        
        addr_from = handler.get('addr_from', 'kunai@mydomain.com')
        smtp_server = handler.get("smtp_server", "localhost")
        smtps = handler.get("smtps", False)
        contacts = handler.get('contacts', ['admin@mydomain.com'])
        subject_p = handler.get('subject_template', 'email.subject.tpl')
        text_p = handler.get('text_template', 'email.text.tpl')
        
        # go connect now
        try:
            print "EMAIL connection to", smtp_server
            s = smtplib.SMTP(smtp_server, timeout=30)
            
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            
            subject_f = os.path.join(self.configuration_dir, 'templates', subject_p)
            text_f = os.path.join(self.configuration_dir, 'templates', text_p)
            
            if not os.path.exists(subject_f):
                logger.error('Missing template file %s' % subject_f)
                return
            if not os.path.exists(text_f):
                logger.error('Missing template file %s' % text_f)
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
            print "SENDING EMAIL", addr_from, contacts, msg
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            logger.error('Cannot send email: %s' % traceback.format_exc())
    
    
    def launch_handlers(self, check, did_change):
        for hname in check['handlers']:
            handler = self.handlers.get(hname, None)
            # maybe some one did atomize this handler? if so skip it :)
            if handler is None:
                continue
            
            # Look at the state and should match severities
            if check['state'] not in handler['severities']:
                continue
            
            # maybe it's a none (untyped) handler, if so skip it
            if handler['type'] == 'none':
                continue
            elif handler['type'] == 'mail':
                if did_change:
                    print "HANDLER EMAIL" * 10, did_change, handler
                    self.send_mail(handler, check)
            else:
                logger.warning('Unknown handler type %s for %s' % (handler['type'], handler['name']))


handlermgr = HandlerManager()
