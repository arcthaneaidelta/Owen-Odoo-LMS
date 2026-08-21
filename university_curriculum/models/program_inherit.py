# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UniversityProgram(models.Model):
    _inherit = 'university.program'

    master_curriculum_ids = fields.One2many(
        'university.curriculum', 
        'program_id', 
        domain=[('curriculum_type', '=', 'master')],
        string='Main Program Curriculums'
    )

    batch_curriculum_ids = fields.One2many(
        'university.curriculum', 
        'program_id', 
        domain=[('curriculum_type', '=', 'batch')],
        string='Batch Wise Curriculums'
    )

    subject_ids = fields.One2many(
        'university.subject',
        'program_id',
        string='Subjects'
    )

    free_subject_ids = fields.Many2many(
        'university.subject',
        compute='_compute_free_subject_ids',
        inverse='_inverse_free_subject_ids',
        string='Manage Subjects',
    )

    subject_count = fields.Integer(
        string='Subject Count',
        compute='_compute_subject_count',
    )

    @api.depends('subject_ids')
    def _compute_subject_count(self):
        for rec in self:
            rec.subject_count = len(rec.subject_ids)

    @api.depends('subject_ids')
    def _compute_free_subject_ids(self):
        for rec in self:
            rec.free_subject_ids = rec.subject_ids

    def _inverse_free_subject_ids(self):
        for rec in self:
            # Any subject removed from free_subject_ids drops its program_id
            removed = rec.subject_ids - rec.free_subject_ids
            removed.write({'program_id': False})
            # Any newly picked subjects adopt this program_id
            rec.free_subject_ids.write({'program_id': rec.id})
