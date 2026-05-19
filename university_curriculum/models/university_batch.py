# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class UniversityBatch(models.Model):
    _inherit = 'university.batch'

    # Curriculum blueprint - locked once batch is active
    curriculum_id = fields.Many2one(
        'university.curriculum',
        string='Curriculum Blueprint',
        tracking=True,
    )
    curriculum_locked = fields.Boolean(
        string='Curriculum Locked',
        default=False,
        help='When True, the curriculum blueprint cannot be changed.',
    )

    def action_activate(self):
        for rec in self:
            if not rec.curriculum_id:
                raise ValidationError(
                    _('Cannot activate a batch without a curriculum blueprint.')
                )
        res = super().action_activate()
        for rec in self:
            rec.write({'curriculum_locked': True})
            rec.message_post(
                body=_('Curriculum blueprint is now locked.')
            )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.curriculum_id and rec.curriculum_id.curriculum_type == 'master':
                rec._generate_batch_curriculum()
        return records

    def write(self, vals):
        if 'curriculum_id' in vals:
            for rec in self:
                if rec.curriculum_locked:
                    raise ValidationError(
                        _(
                            'Cannot change the curriculum blueprint for batch "%s" '
                            'because it is locked (batch is active). '
                            'Create a new batch for curriculum changes.'
                        ) % rec.name
                    )
        
        res = super().write(vals)
        
        if 'curriculum_id' in vals:
            for rec in self:
                if rec.curriculum_id and rec.curriculum_id.curriculum_type == 'master':
                    rec._generate_batch_curriculum()
        
        return res

    def _generate_batch_curriculum(self):
        self.ensure_one()
        if not self.curriculum_id or self.curriculum_id.curriculum_type != 'master':
            return
            
        # Copy the master curriculum
        batch_curr = self.curriculum_id.copy({
            'name': f"{self.curriculum_id.name} - {self.name} Draft",
            'curriculum_type': 'batch',
            'parent_id': self.curriculum_id.id,
            'batch_id': self.id,
            'state': 'draft',
            'is_locked': False,
        })
        
        # Update the batch to point to its own copy
        # Use sudo/super to bypass lock checks if any
        super(UniversityBatch, self).write({'curriculum_id': batch_curr.id})
