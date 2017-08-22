import os
import traceback
import smtplib
import datetime
import time

try:
    import jinja2
except ImportError:
    jinja2 = None

from opsbro.gossip import gossiper
from opsbro.misc.slacker import Slacker
from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('handler')


# TODO: finish the email part

class HandlerManager(object):
    def __init__(self):
        self.handlers = {}
    
    
    def import_handler(self, handler, full_path, file_name, mod_time=0, pack_name='', pack_level=''):
        handler['from'] = full_path
        handler['pack_name'] = pack_name
        handler['pack_level'] = pack_level
        handler['configuration_dir'] = os.path.dirname(full_path)
        handler['name'] = handler['id']
        if 'notes' not in handler:
            handler['notes'] = ''
        handler['modification_time'] = mod_time
        if 'severities' not in handler:
            handler['severities'] = ['ok', 'warning', 'critical', 'unknown']
        # look at types now
        if 'type' not in handler:
            handler['type'] = 'none'
        _type = handler['type']
        if _type == 'mail':
            if 'email' not in handler:
                handler['email'] = 'root@localhost'
        elif _type == 'slack':
            handler['slack_token'] = handler.get('slack_token', os.environ.get('SLACK_TOKEN', ''))
            handler['channel'] = handler.get('channel', '#general')
        
        # Add it into the list
        self.handlers[handler['id']] = handler
    
    
    def send_mail(self, handler, check):
        
        addr_from = handler.get('addr_from', 'opsbro@mydomain.com')
        smtp_server = handler.get("smtp_server", "localhost")
        smtps = handler.get("smtps", False)
        contacts = handler.get('contacts', ['admin@mydomain.com'])
        subject_p = handler.get('subject_template', 'email.subject.tpl')
        text_p = handler.get('text_template', 'email.text.tpl')
        templates_dir = os.path.join(handler.get('configuration_dir', ''), 'templates')
        
        # go connect now
        try:
            logger.debug("Handler: EMAIL connection to %s" % smtp_server)
            s = smtplib.SMTP(smtp_server, timeout=30)
            
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            
            subject_f = os.path.join(templates_dir, subject_p)
            text_f = os.path.join(templates_dir, text_p)
            
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
            logger.debug("Sending email from:%s to %s. Message=%s" % (addr_from, contacts, msg))
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            logger.error('Cannot send email: %s' % traceback.format_exc())
    
    
    def try_to_send_message(self, slack, attachments, channel):
        r = slack.chat.post_message(channel=channel, text='', as_user=True, attachments=attachments)
        logger.debug('[SLACK] return of the send: %s %s %s' % (r.successful, r.__dict__['body']['channel'], r.__dict__['body']['ts']))
    
    
    def send_slack(self, handler, check):
        if not handler['token']:
            logger.error('[SLACK] token is not configured on the handler %s skipping slack messages.' % handler['name'])
            return
        slack = Slacker(handler['token'])
        # title = '{date_num} {time_secs} [node:`%s`][addr:`%s`] Check `%s` is going %s' % (gossiper.display_name, gossiper.addr, check['name'], check['state'])
        content = check['output']
        channel = handler['channel']
        colors = {'ok': 'good', 'warning': 'warning', 'critical': 'danger'}
        node_name = '%s (%s)' % (gossiper.name, gossiper.addr)
        if gossiper.display_name:
            node_name = '%s [%s]' % (node_name, gossiper.display_name)
        attachment = {"pretext": ' ', "text": content, 'color': colors.get(check['state'], '#764FA5'), 'author_name': node_name, 'footer': 'Send by OpsBro on %s' % node_name, 'ts': int(time.time())}
        fields = [
            {"title": "Node", "value": node_name, "short": True},
            {"title": "Check", "value": check['name'], "short": True},
        ]
        attachment['fields'] = fields
        attachments = [attachment]
        try:
            self.try_to_send_message(slack, attachments, channel)
        except Exception, exp:
            logger.error('[SLACK] Cannot send alert: %s (%s) %s %s %s' % (exp, type(exp), str(exp), str(exp) == 'channel_not_found', exp.__dict__))
            # If it's just that the channel do not exists, try to create it
            if str(exp) == 'channel_not_found':
                try:
                    logger.info('[SLACK] Channel %s do no exists. Trying to create it.' % channel)
                    slack.channels.create(channel)
                except Exception, exp:
                    logger.error('[SLACK] Cannot create channel %s: %s' % (channel, exp))
                    return
                # Now try to resend the message
                try:
                    self.try_to_send_message(slack, attachments, channel)
                except Exception, exp:
                    logger.error('[SLACK] Did create channel %s but we still cannot send the message: %s' % (channel, exp))
    
    
    def launch_handlers(self, check, did_change):
        logger.debug('Launch handlers: %s (didchange=%s)' % (check['name'], did_change))
        
        for hname in check['handlers']:
            handler = self.handlers.get(hname, None)
            # maybe some one did atomize this handler? if so skip it :)
            if handler is None:
                logger.warning('Asking for handler %s by check %s but it is not found in my handlers: %s' % (hname, check['name'], self.handlers.keys()))
                continue
            logger.debug('Handler is founded: %s' % handler)
            # Look at the state and should match severities
            if check['state'] not in handler['severities']:
                continue
            
            # maybe it's a none (untyped) handler, if so skip it
            if handler['type'] == 'none':
                continue
            elif handler['type'] == 'mail':
                if did_change:
                    logger.info('Launching email handler for check %s' % check['name'])
                    self.send_mail(handler, check)
            elif handler['type'] == 'slack':
                if did_change:
                    self.send_slack(handler, check)
            else:
                logger.warning('Unknown handler type %s for %s' % (handler['type'], handler['name']))


handlermgr = HandlerManager()
