import time
import os
import traceback
import datetime
import codecs

from opsbro.library import libstore
from opsbro.module import HandlerModule
from opsbro.parameters import BoolParameter, StringParameter, StringListParameter


class MailHandlerModule(HandlerModule):
    implement = 'mail'
    
    parameters = {
        'enabled'                    : BoolParameter(default=False),
        'severities'                 : StringListParameter(default=['ok', 'warning', 'critical', 'unknown']),
        'contacts'                   : StringListParameter(default=['monitoring@mydomain.com']),
        'addr_from'                  : StringParameter(default='opsbro@mydomain.com'),
        'smtp_server'                : StringParameter(default='localhost'),
        'smtps'                      : BoolParameter(default=False),
        'check_subject_template'     : StringParameter(default='mail-check-subject.tpl'),
        'check_text_template'        : StringParameter(default='mail-check-text.tpl'),
        
        'group_subject_template'     : StringParameter(default='mail-group-subject.tpl'),
        'group_text_template'        : StringParameter(default='mail-group-text.tpl'),
        
        'compliance_subject_template': StringParameter(default='mail-compliance-subject.tpl'),
        'compliance_text_template'   : StringParameter(default='mail-compliance-text.tpl'),
        
    }
    
    
    def __init__(self):
        super(MailHandlerModule, self).__init__()
        self.jinja2 = libstore.get_jinja2()
        self.smtplib = None
        
        # Check templates, to load them only once
        self.__computed_templates = {'check'     : {'subject': None, 'text': None},
                                     'group'     : {'subject': None, 'text': None},
                                     'compliance': {'subject': None, 'text': None},
                                     }
    
    
    def __send_email(self, addr_from, msg, about_what):
        
        # Lazy load smtplib
        if self.smtplib is None:
            import smtplib
            self.smtplib = smtplib
        
        smtp_server = self.get_parameter("smtp_server")
        smtps = self.get_parameter("smtps")
        contacts = self.get_parameter('contacts')
        
        try:
            self.logger.debug("Handler: MAIL connection to %s" % smtp_server)
            s = self.smtplib.SMTP(smtp_server, timeout=30)
            r = s.sendmail(addr_from, contacts, msg.as_string())
            s.quit()
            self.logger.info('Did send an email to %d contacts (%s) about %s' % (len(contacts), ','.join(contacts), about_what))
        except Exception:
            self.logger.error('Cannot send mail: %s' % traceback.format_exc())
    
    
    def __get_msg(self, addr_from, subject_m, text_m):
        from email.mime.text import MIMEText
        from email.header import Header
        
        msg = MIMEText(text_m, 'plain', 'utf-8')
        msg['From'] = addr_from
        msg['Subject'] = Header(subject_m, 'utf-8')
        
        return msg
    
    
    def __get_computed_template(self, for_what, which_template):
        what_entry = self.__computed_templates[for_what]
        return what_entry[which_template]
    
    
    def __load_and_compute_one_template(self, for_what, which_template):
        templates_dir = os.path.join(self.pack_directory, 'templates')
        pth = self.get_parameter('%s_%s_template' % (for_what, which_template))
        full_pth = os.path.join(templates_dir, pth)
        if not os.path.exists(full_pth):
            self.logger.error('Missing template file %s_%s_template: %s' % (for_what, which_template, full_pth))
            return False
        try:
            with codecs.open(full_pth, 'r', 'utf8') as f:
                buf = f.read()
        except Exception as exp:
            self.logger.error('Cannot load template file %s_%s_template (%s) : %s' % (for_what, which_template, full_pth, exp))
            return False
        try:
            tpl = self.jinja2.Template(buf)
        except Exception as exp:
            self.logger.error('The template %s_%s_template (%s) did raised an error when parsing: %s' % (for_what, which_template, full_pth, exp))
            return False
        # Ok we can save it
        what_entry = self.__computed_templates[for_what]
        what_entry[which_template] = tpl
        return True
    
    
    def __compute_templates(self, for_what):
        # Maybe it's already computed
        subject_tpl = self.__get_computed_template(for_what, 'subject')
        text_tpl = self.__get_computed_template(for_what, 'text')
        if subject_tpl is not None and text_tpl is not None:
            return True
        
        success = True
        success &= self.__load_and_compute_one_template(for_what, 'subject')
        success &= self.__load_and_compute_one_template(for_what, 'text')
        
        subject_tpl = self.__get_computed_template(for_what, 'subject')
        text_tpl = self.__get_computed_template(for_what, 'text')
        return subject_tpl is not None and text_tpl is not None
    
    
    def send_mail_check(self, check):
        have_templates = self.__compute_templates('check')
        if not have_templates:
            self.logger.error('We do not have templates available, skiping the email sending')
            return
        subject_tpl = self.__get_computed_template('check', 'subject')
        text_tpl = self.__get_computed_template('check', 'text')
        try:
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            subject_m = subject_tpl.render(check=check, _time=_time)
            text_m = text_tpl.render(check=check, _time=_time)
            addr_from = self.get_parameter('addr_from')
            msg = self.__get_msg(addr_from, subject_m, text_m)
            
            self.__send_email(addr_from, msg, 'check state change')
        except:
            self.logger.error('Cannot send mail for check: %s' % traceback.format_exc())
    
    
    def send_mail_group(self, group, group_modification):
        have_templates = self.__compute_templates('group')
        if not have_templates:
            self.logger.error('We do not have templates available, skiping the email sending')
            return
        subject_tpl = self.__get_computed_template('group', 'subject')
        text_tpl = self.__get_computed_template('group', 'text')
        try:
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            subject_m = subject_tpl.render(group=group, group_modification=group_modification)
            text_m = text_tpl.render(group=group, group_modification=group_modification)
            addr_from = self.get_parameter('addr_from')
            msg = self.__get_msg(addr_from, subject_m, text_m)
            
            self.__send_email(addr_from, msg, 'group modification')
        except:
            self.logger.error('Cannot send mail for group modification: %s' % traceback.format_exc())
    
    
    def send_mail_compliance(self, compliance):
        have_templates = self.__compute_templates('compliance')
        if not have_templates:
            self.logger.error('We do not have templates available, skiping the email sending')
            return
        subject_tpl = self.__get_computed_template('compliance', 'subject')
        text_tpl = self.__get_computed_template('compliance', 'text')
        try:
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            subject_m = subject_tpl.render(compliance=compliance, _time=_time)
            text_m = text_tpl.render(compliance=compliance, _time=_time)
            addr_from = self.get_parameter('addr_from')
            msg = self.__get_msg(addr_from, subject_m, text_m)
            
            self.__send_email(addr_from, msg, 'compliance rule state change')
        except:
            self.logger.error('Cannot send mail for compliance modification: %s' % traceback.format_exc())
    
    
    def handle(self, obj, event):
        enabled = self.get_parameter('enabled')
        if not enabled:
            self.logger.debug('Mail module is not enabled, skipping check alert sent')
            return
        
        self.logger.debug('Manage an obj event: %s (event=%s)' % (obj, event))
        
        evt_type = event['evt_type']
        
        # Checks: only notify about changes
        if evt_type == 'check_execution':
            evt_data = event['evt_data']
            check_did_change = evt_data['check_did_change']
            if check_did_change:
                self.send_mail_check(obj)
        
        # We are launched only if the group did change
        if evt_type == 'group_change':
            evt_data = event['evt_data']
            group_modification = evt_data['modification']
            self.send_mail_group(obj, group_modification)
        
        # Compliance: only when change, and only some switch cases should be
        # notify (drop useless changes)
        if evt_type == 'compliance_execution':
            evt_data = event['evt_data']
            compliance_did_change = evt_data['compliance_did_change']
            if compliance_did_change:
                self.send_mail_compliance(obj)
