# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp import netsvc

# class stock_picking(osv.Model):
#     _inherit = 'stock.picking'
# 
#     _columns = {
#         'gate_pass_id': fields.many2one('gate.pass', 'Gate Pass'),
#     }
# 
#     def action_confirm(self, cr, uid, ids, context=None):
#         """ Confirms picking.
#         @return: True
#         """
#         picking_authority_obj = self.pool.get('document.authority.instance')
#         picking = False
#         pickings = self.browse(cr, uid, ids, context=context)
#         self.write(cr, uid, ids, {'state': 'confirmed'})
#         todo = []
#         for picking in pickings:
#             if picking.type == 'internal':
#                 if picking.indent_id and picking.indent_id.employee_id and picking.indent_id.employee_id.coach_id and picking.indent_id.employee_id.coach_id.user_id and picking.indent_id.employee_id.coach_id.user_id.id:
#                     picking_authority_obj.create(cr, uid, {'name': picking.indent_id.employee_id.coach_id.user_id.id, 'document': 'picking', 'picking_id': picking.id, 'priority': 1}, context=context)
#                 if picking.indent_id and picking.indent_id.employee_id and picking.indent_id.employee_id.user_id and picking.indent_id.employee_id.user_id.id:
#                     picking_authority_obj.create(cr, uid, {'name': picking.indent_id.employee_id.user_id.id, 'document': 'picking', 'picking_id': picking.id, 'priority': 2}, context=context)
#             for r in picking.move_lines:
#                 if r.state == 'draft':
#                     todo.append(r.id)
#         todo = self.action_explode(cr, uid, todo, context)
#         if len(todo):
#             picking = self.pool.get('stock.move').action_confirm(cr, uid, todo, context=context)
# 
#         gate_pass_id = self.browse(cr, uid, ids[0], context=context).gate_pass_id.id
#         if gate_pass_id:
#             if isinstance(picking, browse_record):
#                 picking = picking.id
#             self.pool.get('gate.pass').write(cr, uid, [gate_pass_id], {'in_picking_id': picking}, context=context)
#         return picking
# 
# stock_picking()
# 
# class stock_picking_in(osv.Model):
#     _inherit = "stock.picking.in"
# 
#     _columns = {
#         'gate_pass_id': fields.many2one('gate.pass', 'Gate Pass'),
#     }
# 
# stock_picking_in()
# 
# class stock_picking_out(osv.Model):
#     _inherit = "stock.picking.out"
# 
#     _columns = {
#         'gate_pass_id': fields.many2one('gate.pass', 'Gate Pass'),
#     }
# 
# stock_picking_out()

class gate_pass_type(osv.Model):
    _name = 'gatepass.type'
    _description = 'Gate Pass Type'

    _columns = {
        'name': fields.char('Name', size=256, select=1),
        'code': fields.char('Code', size=16, select=1),
        'approval_required': fields.boolean('Approval State'),
        'return_type': fields.selection([('return', 'Returnable'), ('non_return', 'Non-Returnable')], 'Return Type', required=True),
        'active': fields.boolean('Active')
    }

    _defaults = {
        'active': True,
        'return_type': 'return'
    }

gate_pass_type()

class stock_gatepass(osv.Model):
    _name = 'stock.gatepass'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Gate Pass'
    _order = "name desc"

    def _get_total_amount(self, cr, uid, ids, name, args, context=None):
        result = {}
        for gatepass in self.browse(cr, uid, ids, context=context):
            total = 0.0
            for line in gatepass.line_ids:
                total += (line.product_qty * line.price_unit)
            result[gatepass.id] = total
        return result

    def onchange_indent(self, cr, uid, ids, indent=False, *args, **kw):
        result = {'line_ids': []}
        lines = []

        if not indent:
            return {'value': result}
        products = self.pool.get('indent.indent').browse(cr, uid, indent).product_lines
        location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        location = location_id and location_id[1] or False
        for product in products:
            vals = dict(product_id=product.original_product_id.id or product.product_id.id or False, product_uom_qty=product.product_uom_qty, product_uom=product.product_uom.id, name=product.product_id.name, location_id=location, location_dest_id=location, app_rate=product.price_unit)
            lines.append(vals)
        result['line_ids'] = lines
        return {'value': result}

    def onchange_type(self, cr, uid, ids, type_id=False):
        result = {}
        if type_id:
            type = self.pool.get('gatepass.type').browse(cr, uid, type_id)
            result['return_type'] = type.return_type
        return {'value': result}

    _columns = {
        'name': fields.char('Name', size=256, readonly=True),
        'driver_id': fields.many2one('res.partner', 'Driver'),
        'person_id': fields.many2one('res.partner', 'Delivery Person'),
        'picking_in_id': fields.many2one('stock.picking.in', 'Inward'),
        'picking_out_id': fields.many2one('stock.picking.out', 'Delivery Order'),
        'date': fields.datetime('Date', required=True),
        'approve_date': fields.datetime('Approve Date'),
        'type_id': fields.many2one('gatepass.type', 'Type', required=True),
        'purchase_id': fields.many2one('purchase.order', 'Order'),
        'indent_id': fields.many2one('indent.indent', 'Indent'),
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True),
        'line_ids': fields.one2many('stock.gatepass.line', 'gatepass_id', 'Products'),
        'description': fields.text('Remarks'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'amount_total': fields.function(_get_total_amount, type="float", string='Total', store=True),
        'location_id': fields.many2one('stock.location', 'Source Location'),
        'state':fields.selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('pending', 'Pending'), ('done', 'Done')], 'State', readonly=True),
        'return_type': fields.selection([('return', 'Returnable'), ('non_return', 'Non Returnable')], 'Return Type', required=True),
    }

    _defaults = {
        'state': 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'gate.pass', context=c)
    }

#     def unlink(self, cr, uid, ids, context=None):
#         for gp in self.browse(cr, uid, ids, context=context):
#             if gp.state not in ('draft'):
#                 raise osv.except_osv(_('Invalid Action!'), _('You cannot delete a gate pass which is in \'%s\' state.') % gp.state)
#         return super(gate_pass, self).unlink(cr, uid, ids, context=context)

    def create_delivery_order(self, cr, uid, ids, context=None):
        picking_out_obj = self.pool.get('stock.picking.out')
        move_obj = self.pool.get('stock.move')
        picking_ids = []
        for gatepass in self.browse(cr, uid, ids, context=context):
            vals = {
                'partner_id': gatepass.partner_id.id,
                'gate_pass_id': gatepass.id,
                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'origin': gatepass.name,
                'type': 'out',
            }
            out_picking_id = picking_out_obj.create(cr, uid, vals, context=context)
            picking_ids.append(out_picking_id)
            self.write(cr, uid, [gatepass.id], {'out_picking_id': out_picking_id}, context=context)
            for line in gatepass.gate_pass_lines:
                result = dict(name=line.product_id.name, product_id=line.product_id.id, product_qty=line.product_uom_qty, product_uom=line.product_uom.id, location_id=line.location_id.id, location_dest_id=line.location_dest_id.id, picking_id=out_picking_id)
                move_obj.create(cr, uid, result, context=context)
        return picking_ids

    def open_delivery_order(self, cr, uid, ids, context=None):
        out_picking_id = self.browse(cr, uid, ids[0], context=context).out_picking_id.id
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
        result = {
            'name': _('Delivery Order'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': res and res[1] or False,
            'res_model': 'stock.picking.out',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': out_picking_id,
        }
        return result

    def open_incoming_shipment(self, cr, uid, ids, context=None):
        in_picking_id = self.browse(cr, uid, ids[0], context=context).in_picking_id.id
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_in_form')
        result = {
            'name': _('Incoming Shipment'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': res and res[1] or False,
            'res_model': 'stock.picking.in',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': in_picking_id,
        }
        return result

    def check_returnable(self, cr, uid, ids, context=None):
        for gp in self.browse(cr, uid, ids, context=context):
            if gp.type_id.return_type == 'return':
                return True
        return False

    def action_confirm(self, cr, uid, ids, context=None):
        seq_obj = self.pool.get('ir.sequence')
        picking_obj = self.pool.get('stock.picking')
        
        wf_service = netsvc.LocalService("workflow")

        picking_ids = self.create_delivery_order(cr, uid, ids, context=context)
        
        if picking_ids:
            picking = picking_ids[0]
            wf_service.trg_validate(uid, 'stock.picking', picking, 'button_confirm', cr)
            picking_obj.action_move(cr, uid, [picking], context=context)
            wf_service.trg_validate(uid, 'stock.picking', picking, 'button_done', cr)
            
            seq_name = 'gate.pass.purchase'
        
            name = False
            name = seq_obj.get(cr, uid, seq_name)
            return self.write(cr, uid, ids, {'state': 'confirm','name':name}, context=context)
        
        return False
    
    def action_picking_create(self, cr, uid, ids, context=None):
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking.in')
        purchase_id = False

        gatepass = self.browse(cr, uid, ids[0], context=context)
        picking = gatepass.in_picking_id.id
        if not picking:
            raise osv.except_osv(_("Error !"), _('An inward related to the gate pass is not created.'))
        indent_id = gatepass.indent_id and gatepass.indent_id.id or False
        line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('indent_id', '=', indent_id)], context=context)
        line_id = line_ids and line_ids[0] or False
        if line_id:
            purchase_id = self.pool.get('purchase.order.line').browse(cr, uid, line_id, context=context).order_id.id
        picking_obj.write(cr, uid, [picking], {'gate_pass_id': ids[0], 'purchase_id': purchase_id}, context=context)
        move_ids = [move.id for move in picking_obj.browse(cr, uid, picking, context=context).move_lines]
        move_obj.write(cr, uid, move_ids, {'indent_id': indent_id}, context=context)
        self.write(cr, uid, ids, {'state': 'pending'}, context=context)
        return picking

stock_gatepass()

class stock_gatepass_line(osv.Model):
    _name = 'stock.gatepass.line'
    _description = 'Gate Pass Lines'

    def _get_subtotal_amount(self, cr, uid, ids, name, args, context=None):
        result = {}
        for gp in self.browse(cr, uid, ids, context=context):
            result[gp.id] = (gp.product_qty * gp.price_unit)
        return result
  
    _columns = {
        'name': fields.text('Name', required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True),
        
        'gatepass_id': fields.many2one('stock.gatepass', 'Gate Pass', required=True, ondelete='cascade'),
        'product_qty': fields.float('Quantity', required=True),
        
        'location_id': fields.many2one('stock.location', 'Source Location', required=True),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', required=True),
        
        'price_unit': fields.float('Approx. Value'),
        'prodlot_id': fields.many2one('stock.production.lot', 'Serial #', domain="[('product_id','=',product_id)]"),
     }

    def _get_uom_id(self, cr, uid, *args):
        result = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product', 'product_uom_unit')
        return result and result[1] or False

    def _default_stock_location(self, cr, uid, context=None):
        stock_location = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'stock_location_stock')
        return stock_location.id

    _defaults = {
        'product_qty': 1,
        'uom_id': _get_uom_id,
        'location_id': _default_stock_location,
        'location_dest_id': _default_stock_location,
    }

    def onchange_product_id(self, cr, uid, ids, product_id=False):
        result = {}
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id)
            result = dict(value=dict(name=product.name, product_uom=product.uom_id and product.uom_id.id or False, app_rate=product.list_price))
        return result

stock_gatepass_line()

# class stock_move(osv.Model):
#     _inherit = 'stock.move'
# 
#     def _create_chained_picking(self, cr, uid, picking_name, picking, picking_type, moves_todo, context=None):
#         picking_obj = self.pool.get('stock.picking')
#         return picking_obj.create(cr, uid, self._prepare_chained_picking(cr, uid, picking_name, picking, picking_type, moves_todo, context=context))
# 
#     def create_chained_picking(self, cr, uid, moves, context=None):
#         res_obj = self.pool.get('res.company')
#         location_obj = self.pool.get('stock.location')
#         move_obj = self.pool.get('stock.move')
#         wf_service = netsvc.LocalService("workflow")
#         pickid = False
#         new_moves = []
#         if context is None:
#             context = {}
#         seq_obj = self.pool.get('ir.sequence')
#         for picking, todo in self._chain_compute(cr, uid, moves, context=context).items():
#             ptype = todo[0][1][5] and todo[0][1][5] or location_obj.picking_type_get(cr, uid, todo[0][0].location_dest_id, todo[0][1][0])
#             if picking:
#                 # name of new picking according to its type
#                 new_pick_name = seq_obj.get(cr, uid, 'stock.picking.' + ptype)
#                 pickid = self._create_chained_picking(cr, uid, new_pick_name, picking, ptype, todo, context=context)
#                 # Need to check name of old picking because it always considers picking as "OUT" when created from Sales Order
#                 old_ptype = location_obj.picking_type_get(cr, uid, picking.move_lines[0].location_id, picking.move_lines[0].location_dest_id)
#                 if old_ptype != picking.type:
#                     old_pick_name = seq_obj.get(cr, uid, 'stock.picking.' + old_ptype)
#                     self.pool.get('stock.picking').write(cr, uid, [picking.id], {'name': old_pick_name, 'type': old_ptype}, context=context)
#             else:
#                 pickid = False
#             for move, (loc, dummy, delay, dummy, company_id, ptype, invoice_state) in todo:
#                 new_id = move_obj.copy(cr, uid, move.id, {
#                     'location_id': move.location_dest_id.id,
#                     'location_dest_id': loc.id,
#                     'date': time.strftime('%Y-%m-%d'),
#                     'picking_id': pickid,
#                     'state': 'waiting',
#                     'company_id': company_id or res_obj._company_default_get(cr, uid, 'stock.company', context=context)  ,
#                     'move_history_ids': [],
#                     'date_expected': (datetime.strptime(move.date, '%Y-%m-%d %H:%M:%S') + relativedelta(days=delay or 0)).strftime('%Y-%m-%d'),
#                     'move_history_ids2': []}
#                 )
#                 move_obj.write(cr, uid, [move.id], {
#                     'move_dest_id': new_id,
#                     'move_history_ids': [(4, new_id)]
#                 })
#                 new_moves.append(self.browse(cr, uid, [new_id])[0])
#             if pickid:
#                 wf_service.trg_validate(uid, 'stock.picking', pickid, 'button_confirm', cr)
#         if new_moves:
#             new_moves += self.create_chained_picking(cr, uid, new_moves, context)
#         return new_moves, pickid
# 
#     def action_confirm(self, cr, uid, ids, context=None):
#         """ Confirms stock move.
#         @return: List of ids.
#         """
#         moves = self.browse(cr, uid, ids, context=context)
#         self.write(cr, uid, ids, {'state': 'confirmed'})
#         moves, picking = self.create_chained_picking(cr, uid, moves, context)
#         return picking
# 
# stock_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: