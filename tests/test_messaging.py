"""test_messaging

Tests for external messaging

created 18-jan-2021 by richb@instantlinux.net
"""

import smtplib
from unittest import mock

from apicrud import APIcrudSendError
from apicrud.messaging.send import Messaging

import test_base


class TestMessaging(test_base.TestBase):

    @mock.patch('smtplib.SMTP', autospec=True)
    def test_send_smtp(self, mock_smtp):

        Messaging().send(frm=self.test_uid, to=self.adm_contact_id,
                         template='moderator', list='test',
                         message='hello world')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().starttls')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().sendmail')
        self.assertEqual({}, kwargs)

        _from, _to, _body = args
        self.assertEqual('user@example.com', _from)
        self.assertEqual('admin@test.conclave.events', _to)
        self.assertIn("List: test\n\nhello world", _body)

    @mock.patch('smtplib.SMTP', autospec=True)
    def test_send_sms(self, mock_smtp):
        self.authorize()
        record = dict(uid=self.test_uid, type='sms', info='6178765309',
                      carrier='att', label='mobile', privacy='public')
        response = self.call_endpoint('/contact', 'post', record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        token = response.get_json()['token']
        response = self.call_endpoint('/contact/confirm/%s' % token, 'post')
        self.assertEqual(response.status_code, 200)

        Messaging().send(frm=record['uid'], to=id, template='moderator',
                         list='testers', message='lorem ipsum')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().starttls')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().sendmail')
        self.assertEqual({}, kwargs)

        _from, _to, _body = args
        self.assertEqual('6178765309@txt.att.net', _to)
        self.assertIn("lorem ipsum", _body)

    @mock.patch('smtplib.SMTP', autospec=True)
    def test_from_approved_sender(self, mock_smtp):
        person = dict(name='J.D. Marketer', identity='jdm@conclave.events')
        list1 = dict(name=self.config.APPROVED_SENDERS,
                     category_id=self.cat_id,
                     privacy='secret', uid=self.global_admin_id)

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/person', 'post', person)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['id']
        list1['members'] = [uid]
        response = self.call_endpoint('/list', 'post', data=list1)
        self.assertEqual(response.status_code, 201)

        Messaging().send(frm=uid, to=self.adm_contact_id,
                         template='moderator', list='test',
                         message='lorem ipsum')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().starttls')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().sendmail')
        self.assertEqual({}, kwargs)

        _from, _to, _body = args
        self.assertEqual(person['identity'], _from)

    @mock.patch('smtplib.SMTP', autospec=True)
    def test_send_with_credential(self, mock_smtp):
        record = dict(name='gmail', vendor='google', uid=self.test_uid,
                      key='thejoker@gmail.com',
                      secret='darkweb1', settings_id=self.settings_id)

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/credential', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/settings/%s' % self.settings_id, 'get')
        self.assertEqual(response.status_code, 200)
        settings = response.get_json()
        settings['smtp_credential_id'] = id
        settings.pop('created', None)
        settings.pop('modified', None)
        settings.pop('rbac', None)
        response = self.call_endpoint('/settings/%s' % self.settings_id, 'put',
                                      data=settings)
        self.assertEqual(response.status_code, 200)

        Messaging().send(frm=self.test_uid, to=self.adm_contact_id,
                         template='moderator', list='test',
                         message='best test rest')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().starttls')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().login')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().sendmail')
        self.assertEqual({}, kwargs)

        _from, _to, _body = args
        self.assertIn("List: test\n\nbest test rest", _body)

        mock_smtp.return_value.login.side_effect = (
            smtplib.SMTPAuthenticationError(code=403, msg='unauthorized'))
        with self.assertRaises(APIcrudSendError) as ex:
            Messaging().send(frm=self.test_uid, to=self.adm_contact_id,
                             template='moderator', list='test',
                             message='bad credential')
        self.assertEqual(ex.exception.args,
                         ("Credential problem: (403, 'unauthorized')",))

        # this just restores settings to avoid conflict with other tests
        settings['smtp_credential_id'] = None
        response = self.call_endpoint('/settings/%s' % self.settings_id, 'put',
                                      data=settings)
        self.assertEqual(response.status_code, 200)

    @mock.patch('logging.warning')
    @mock.patch('smtplib.SMTP', autospec=True)
    def test_send_missing_from(self, mock_smtp, mock_logging):
        person = dict(name='Miss Speller', identity='miss@conclave.events')
        record = dict(type='sms', info='8885555309',
                      carrier='att', label='mobile', privacy='invitee')
        expected = dict(message='missing contact type', action='_get_frm',
                        from_id=self.admin_uid, to='8885555309')

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/person', 'post', person)
        self.assertEqual(response.status_code, 201)
        record['uid'] = response.get_json()['id']

        response = self.call_endpoint('/contact', 'post', record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']

        Messaging().send(frm=self.admin_uid, to=id, template='moderator',
                         list='test', message='unsent')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().starttls')
        name, args, kwargs = mock_smtp.method_calls.pop(0)
        self.assertEqual(name, '().sendmail')
        self.assertEqual({}, kwargs)
        _from, _to, _body = args
        self.assertEqual('8885555309@txt.att.net', _to)
        self.assertIn('unsent', _body)

        mock_logging.assert_has_calls([mock.call(expected)])

    @mock.patch('logging.info')
    @mock.patch('smtplib.SMTP', autospec=True)
    def test_send_disabled_contact(self, mock_smtp, mock_logging):
        email = 'hidden-adm@test.conclave.events'
        record = dict(status='disabled', info=email, type='email')
        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/contact/%s' % self.adm_contact_2,
                                      'put', data=record)
        self.assertEqual(response.status_code, 200)

        Messaging().send(frm=self.test_uid, to=self.adm_contact_2,
                         template='moderator', list='tester2',
                         message='keep quiet')
        mock_smtp.assert_not_called()
        mock_logging.assert_called_with(dict(
            action='send_contact', to_id=self.adm_contact_2,
            from_id=self.test_uid, info=email, status='disabled'))

        # restore contact to original status
        record['status'] = 'active'
        response = self.call_endpoint('/contact/%s' % self.adm_contact_2,
                                      'put', data=record)
        self.assertEqual(response.status_code, 200)
