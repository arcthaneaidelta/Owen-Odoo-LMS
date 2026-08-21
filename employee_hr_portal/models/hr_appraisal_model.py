# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HrAppraisal(models.Model):
    _inherit = 'hr.appraisal'

    def create(self, vals):
        record = super(HrAppraisal, self).create(vals)
        record._notify_users()
        return record

    def create_appraisalse(self):
        res = super(HrAppraisal, self).create_appraisalse()
        for order in self:
            order._notify_users(action='new')
        return res

    def _notify_users(self, action='create'):
        """Notify the selected managers by sending a message to their private chat channel."""
        for appraisal in self:
            emp_partner_id = appraisal.employee_id.user_id.partner_id.id if appraisal.employee_id.user_id else False
            if not emp_partner_id:
                _logger.warning("Employee %s has no associated user/partner. Skipping notification.", appraisal.employee_id.name)
                continue

            for manager in appraisal.manager_ids:
                mgr_partner_id = manager.user_id.partner_id.id if manager.user_id else False
                if not mgr_partner_id:
                    _logger.warning("Manager %s has no associated user/partner. Skipping notification.", manager.name)
                    continue

                # Search for an existing private chat channel between employee and manager
                domain = [
                    ('channel_type', '=', 'chat'),
                    ('channel_member_ids.partner_id', 'in', [emp_partner_id, mgr_partner_id]),
                ]
                channels = self.env['discuss.channel'].sudo().search(domain)
                channel = False
                for ch in channels:
                    if set(ch.channel_member_ids.partner_id.ids) == {emp_partner_id, mgr_partner_id}:
                        channel = ch
                        break

                # If no channel exists, create a new private chat channel
                if not channel:
                    channel = self.env['discuss.channel'].sudo().create({
                        'channel_type': 'chat',
                        'channel_member_ids': [
                            (0, 0, {'partner_id': emp_partner_id}),
                            (0, 0, {'partner_id': mgr_partner_id}),
                        ]
                    })

                # Post the notification message in the channel
                body = _("A new appraisal has been created for %s with closing date %s. Please review.") % (appraisal.employee_id.name, appraisal.date_close)
                if action == 'new':
                    body = _("A new appraisal request has been submitted for %s. Please check.") % appraisal.employee_id.name

                channel.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )



class AdvanceRequests(models.Model):
    _inherit = 'advance.requests'

    @api.model
    def create(self, vals):
        record = super(AdvanceRequests, self).create(vals)
        if not self.env.context.get('import_file'):
            record._notify_users()
        return record

    def _notify_users(self, action='create'):
        for advance in self:
            emp_partner_id = advance.employee_id.user_id.partner_id.id if advance.employee_id.user_id else False
            if not emp_partner_id:
                _logger.warning("Employee %s has no associated user/partner. Skipping notification.", advance.employee_id.name)
                continue

            manager = advance.employee_id.parent_id
            if not manager:
                _logger.warning("Employee %s has no manager. Skipping notification.", advance.employee_id.name)
                continue

            mgr_partner_id = manager.user_id.partner_id.id if manager.user_id else False
            if not mgr_partner_id:
                _logger.warning("Manager %s has no associated user/partner. Skipping notification.", manager.name)
                continue

            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [emp_partner_id, mgr_partner_id]),
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            channel = False
            for ch in channels:
                if set(ch.channel_member_ids.partner_id.ids) == {emp_partner_id, mgr_partner_id}:
                    channel = ch
                    break

            if not channel:
                channel = self.env['discuss.channel'].sudo().create({
                    'channel_type': 'chat',
                    'channel_member_ids': [
                        (0, 0, {'partner_id': emp_partner_id}),
                        (0, 0, {'partner_id': mgr_partner_id}),
                    ]
                })

            body = _("A new advance request has been created by %s for amount %s. Please review.") % (advance.employee_id.name, advance.amount)
            if action == 'new':
                body = _("A new advance request has been submitted by %s. Please check.") % advance.employee_id.name

            channel.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

import logging
from odoo import models, api, _

_logger = logging.getLogger(__name__)

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.model
    def create(self, vals):
        record = super(HrLeave, self).create(vals)
        if not self.env.context.get('import_file'):
            record._notify_users()
        return record

    def _notify_users(self, action='create'):
        """Notify the employee's manager by sending a message to their private chat channel."""
        for leave in self:
            emp_partner_id = leave.employee_id.user_id.partner_id.id if leave.employee_id.user_id else False
            if not emp_partner_id:
                _logger.warning("Employee %s has no associated user/partner. Skipping notification.", leave.employee_id.name)
                continue

            manager = leave.employee_id.parent_id
            if not manager:
                _logger.warning("Employee %s has no manager. Skipping notification.", leave.employee_id.name)
                continue

            mgr_partner_id = manager.user_id.partner_id.id if manager.user_id else False
            if not mgr_partner_id:
                _logger.warning("Manager %s has no associated user/partner. Skipping notification.", manager.name)
                continue

            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [emp_partner_id, mgr_partner_id]),
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            channel = False
            for ch in channels:
                if set(ch.channel_member_ids.partner_id.ids) == {emp_partner_id, mgr_partner_id}:
                    channel = ch
                    break

            if not channel:
                channel_name = f"{leave.employee_id.name} - {manager.name}"
                channel = self.env['discuss.channel'].sudo().create({
                    'channel_type': 'chat',
                    'name': channel_name,
                    'channel_member_ids': [
                        (0, 0, {'partner_id': emp_partner_id}),
                        (0, 0, {'partner_id': mgr_partner_id}),
                    ]
                })

            body = _("A new leave request has been created by %s from %s to %s. Please review.") % (
                leave.employee_id.name, leave.request_date_from, leave.request_date_to)
            if action == 'new':
                body = _("A new leave request has been submitted by %s. Please check.") % leave.employee_id.name

            channel.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

class HrOvertimeRequests(models.Model):
    _inherit = 'hr.overtime.requests'

    @api.model
    def create(self, vals):
        record = super(HrOvertimeRequests, self).create(vals)
        if not self.env.context.get('import_file'):
            record._notify_users()
        return record

    def _notify_users(self, action='create'):
        """Notify the employee's manager by sending a message to their private chat channel."""
        for overtime in self:
            emp_partner_id = overtime.employee_id.user_id.partner_id.id if overtime.employee_id.user_id else False
            if not emp_partner_id:
                _logger.warning("Employee %s has no associated user/partner. Skipping notification.", overtime.employee_id.name)
                continue

            manager = overtime.employee_id.parent_id
            if not manager:
                _logger.warning("Employee %s has no manager. Skipping notification.", overtime.employee_id.name)
                continue

            mgr_partner_id = manager.user_id.partner_id.id if manager.user_id else False
            if not mgr_partner_id:
                _logger.warning("Manager %s has no associated user/partner. Skipping notification.", manager.name)
                continue

            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [emp_partner_id, mgr_partner_id]),
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            channel = False
            for ch in channels:
                if set(ch.channel_member_ids.partner_id.ids) == {emp_partner_id, mgr_partner_id}:
                    channel = ch
                    break

            if not channel:
                channel = self.env['discuss.channel'].sudo().create({
                    'channel_type': 'chat',
                    'channel_member_ids': [
                        (0, 0, {'partner_id': emp_partner_id}),
                        (0, 0, {'partner_id': mgr_partner_id}),
                    ]
                })

            body = _("A new overtime request has been created by %s on %s. Please review.") % (overtime.employee_id.name, overtime.requested_date)
            if action == 'new':
                body = _("A new overtime request has been submitted by %s. Please check.") % overtime.employee_id.name

            channel.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )



class MissingPunch(models.Model):
    _inherit = 'missing.punch'

    @api.model
    def create(self, vals):
        record = super(MissingPunch, self).create(vals)
        if not self.env.context.get('import_file'):
            record._notify_users()
        return record

    def _notify_users(self, action='create'):
        """Notify the employee's missing punch approver (or manager if approver not set) by sending a message to their private chat channel."""
        for punch in self:
            emp_partner_id = punch.employee_id.user_id.partner_id.id if punch.employee_id.user_id else False
            if not emp_partner_id:
                _logger.warning("Employee %s has no associated user/partner. Skipping notification.", punch.employee_id.name)
                continue

            approver = punch.employee_id.missing_punch_approver_id or punch.employee_id.parent_id
            if not approver:
                _logger.warning("Employee %s has no missing punch approver or manager. Skipping notification.", punch.employee_id.name)
                continue

            appr_partner_id = approver.user_id.partner_id.id if approver.user_id else False
            if not appr_partner_id:
                _logger.warning("Approver/Manager %s has no associated user/partner. Skipping notification.", approver.name)
                continue

            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_member_ids.partner_id', 'in', [emp_partner_id, appr_partner_id]),
            ]
            channels = self.env['discuss.channel'].sudo().search(domain)
            channel = False
            for ch in channels:
                if set(ch.channel_member_ids.partner_id.ids) == {emp_partner_id, appr_partner_id}:
                    channel = ch
                    break

            if not channel:
                channel_name = f"{punch.employee_id.name} - {approver.name} (Missing Punch Chat)"
                channel = self.env['discuss.channel'].sudo().create({
                    'channel_type': 'chat',
                    'name': channel_name,
                    'channel_member_ids': [
                        (0, 0, {'partner_id': emp_partner_id}),
                        (0, 0, {'partner_id': appr_partner_id}),
                    ]
                })

            body = _("A new missing punch request has been created by %s for %s. Please review.") % (punch.employee_id.name, punch.punch_datetime)
            if action == 'new':
                body = _("A new missing punch request has been submitted by %s. Please check.") % punch.employee_id.name

            channel.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )