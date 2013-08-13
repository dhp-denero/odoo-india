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
import json
import httplib
        
from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from bsddb.dbtables import _columns

class account_tax(osv.Model):
    _name = 'account.tax'
    _inherit = 'account.tax'
    _columns = {
        'tax_type': fields.selection(
        [('excise', 'Excise'),
         ('cess', 'Education Cess'),
         ('hedu_cess', 'Higher Education Cess'),
         ('vat', 'VAT'),
         ('add_vat','Additional VAT'),
         ('cst', 'CST'),
         ('service', 'Service'),
         ('other', 'Other'),
        ], 'Tax Category', required=True)
    }

    def onchange_tax_type(self, cr, uid, ids, name, tax_type=False, context=None):
        record = self.browse(cr, uid, ids, context)
        result = {}
        vals = []
        if tax_type == 'excise':
            
            vals = [{'name':'Edu.cess 2% on '+name,
                    'tax_type':'cess',
                    'sequence':1,
                    'type':'percent',
                    'amount':0.02,
                    'include_base_amount':False,
                    'type_tax_use':'all',
                   },{'name':'Edu.cess 1% on '+name,
                    'tax_type':'hedu_cess',
                    'sequence':1,
                    'type':'percent',
                    'amount':0.01,
                    'include_base_amount':False,
                    'type_tax_use':'all',
                    }]
        result['child_ids'] = vals
        result['include_base_amount'] = True
        return {'value': result}
    
    def _unit_compute(self, cr, uid, taxes, price_unit, product=None, partner=None, quantity=0):
        taxes = self._applicable(cr, uid, taxes, price_unit , product, partner)
        res = []
        cur_price_unit = price_unit
        for tax in taxes:
            # we compute the amount for the current tax object and append it to the result
            data = {'id':tax.id,
                    'name':tax.description and tax.description + " - " + tax.name or tax.name,
                    'account_collected_id':tax.account_collected_id.id,
                    'account_paid_id':tax.account_paid_id.id,
                    'account_analytic_collected_id': tax.account_analytic_collected_id.id,
                    'account_analytic_paid_id': tax.account_analytic_paid_id.id,
                    'base_code_id': tax.base_code_id.id,
                    'ref_base_code_id': tax.ref_base_code_id.id,
                    'sequence': tax.sequence,
                    'base_sign': tax.base_sign,
                    'tax_sign': tax.tax_sign,
                    'ref_base_sign': tax.ref_base_sign,
                    'ref_tax_sign': tax.ref_tax_sign,
                    'price_unit': cur_price_unit,
                    'tax_code_id': tax.tax_code_id.id,
                    'ref_tax_code_id': tax.ref_tax_code_id.id,
                    'include_base_amount': tax.include_base_amount,
                    'parent_id':tax.parent_id
            }
            res.append(data)
            if tax.type == 'percent':
                amount = cur_price_unit * tax.amount
                data['amount'] = amount

            elif tax.type == 'fixed':
                data['amount'] = tax.amount
                data['tax_amount'] = quantity
                # data['amount'] = quantity
            elif tax.type == 'code':
                localdict = {'price_unit':cur_price_unit, 'product':product, 'partner':partner}
                exec tax.python_compute in localdict
                amount = localdict['result']
                data['amount'] = amount
            elif tax.type == 'balance':
                data['amount'] = cur_price_unit - reduce(lambda x, y: y.get('amount', 0.0) + x, res, 0.0)
                data['balance'] = cur_price_unit

            amount2 = data.get('amount', 0.0)
            if tax.child_ids:
                if tax.child_depend:
                    latest = res.pop()
                amount = amount2
                child_tax = self._unit_compute(cr, uid, tax.child_ids, amount, product, partner, quantity)
                # Add Parent reference in child dictionary of tax so that we can inlcude tha amount of child ...
                for ctax in child_tax:
                    ctax['parent_tax'] = tax.id
                
                res.extend(child_tax)
                if tax.child_depend:
                    for r in res:
                        for name in ('base', 'ref_base'):
                            if latest[name + '_code_id'] and latest[name + '_sign'] and not r[name + '_code_id']:
                                r[name + '_code_id'] = latest[name + '_code_id']
                                r[name + '_sign'] = latest[name + '_sign']
                                r['price_unit'] = latest['price_unit']
                                latest[name + '_code_id'] = False
                        for name in ('tax', 'ref_tax'):
                            if latest[name + '_code_id'] and latest[name + '_sign'] and not r[name + '_code_id']:
                                r[name + '_code_id'] = latest[name + '_code_id']
                                r[name + '_sign'] = latest[name + '_sign']
                                r['amount'] = data['amount']
                                latest[name + '_code_id'] = False
            if tax.include_base_amount:
                cur_price_unit += amount2
                # Check for Child tax addition. If Tax has childrens and they have also set include in base amount we will add it for next tax calculation...
                for r in res:
                    if 'parent_tax' in r and r['parent_tax'] == tax.id:
                        cur_price_unit += r['amount']
        return res

account_tax()

class account_invoice_tax(osv.osv):
    _inherit = 'account.invoice.tax'

    _columns = {
        'tax_categ': fields.selection(
        [('excise', 'Excise'),
         ('cess', 'Cess'),
         ('hedu_cess', 'Higher Education Cess'),
         ('vat', 'VAT'),
         ('add_vat','Additional VAT'),
         ('cst', 'CST'),
         ('other', 'Other'),
         ('service', 'Service'),
        ], 'Tax Category')
    }

    _defaults = {
        'tax_categ': 'other',
    }

    def compute(self, cr, uid, invoice_id, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id
        for line in inv.invoice_line:
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, (line.price_unit) * ((1 - (line.discount or 0.0) / 100.0)), line.quantity, line.product_id, inv.partner_id)['taxes']:
                tax_id = tax['id']
                val = {}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['quantity'])
                val['tax_categ'] = tax_obj.browse(cr, uid, tax_id, context=context).tax_type
                if inv.type in ('out_invoice', 'in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or line.account_id.id
                    val['account_analytic_id'] = tax['account_analytic_collected_id']
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_paid_id'] or line.account_id.id
                    val['account_analytic_id'] = tax['account_analytic_paid_id']
                key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    pass
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']
        
        for t in tax_grouped.values():
            t['base'] = cur_obj.round(cr, uid, cur, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return tax_grouped

class res_company(osv.Model):
    _inherit = 'res.company'
    _columns = {
        'account_ip':fields.char('Account Server', size=64),
        'account_port':fields.integer('Port'),
    }

class account_move(osv.osv):
    _inherit = "account.move"
    _columns = {
        'maize_id':fields.char("Maize Voucher Code", size=64, help="Maize voucher code allocated by maize accounting server")
    }

class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        'series':fields.char("Series", size=64, help="Maize series that used to generate the next number for the accounting vouchers")
    }

class account_invoice(osv.Model):
    _inherit = "account.invoice"

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            res[invoice.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'net_amount': 0.0,
            }
            for line in invoice.invoice_line:
                res[invoice.id]['amount_untaxed'] += line.price_subtotal
            for line in invoice.tax_line:
                res[invoice.id]['amount_tax'] += line.amount
            
            res[invoice.id]['amount_total'] = res[invoice.id]['amount_tax'] + res[invoice.id]['amount_untaxed'] + invoice.freight + invoice.insurance + invoice.other_charges

            res[invoice.id]['amount_total'] = res[invoice.id]['amount_tax'] + res[invoice.id]['amount_untaxed'] + invoice.freight + \
                invoice.package_and_forwording + invoice.insurance + invoice.loading_charges + invoice.inspection_charges + invoice.delivery_charges \
                + invoice.other_charges - invoice.rounding_shortage

            res[invoice.id]['net_amount'] = res[invoice.id]['amount_total'] - (invoice.debit_note_amount + invoice.advance_amount + invoice.retention_amount) 
        return res

    def _get_invoice_line(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context):
            result[line.invoice_id.id] = True
        return result.keys()

    def _get_invoice_tax(self, cr, uid, ids, context=None):
        result = {}
        for tax in self.pool.get('account.invoice.tax').browse(cr, uid, ids, context=context):
            result[tax.invoice_id.id] = True
        return result.keys()

    _columns = {
        'freight': fields.float('Freight'),
        'other_charges': fields.float('Other Charges'),
        'insurance': fields.float('Insurance'),
        'amount_untaxed': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Subtotal', track_visibility='always',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line', 'freight', 'insurance', 'other_charges', 'package_and_forwording', 'loading_charges', 'inspection_charges', 'delivery_charges', 'rounding_shortage'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'amount_tax': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Tax',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line', 'freight', 'insurance', 'other_charges'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'amount_total': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Total',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line', 'freight', 'insurance', 'other_charges', 'package_and_forwording', 'loading_charges', 'inspection_charges', 'delivery_charges', 'rounding_shortage'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'carting':fields.selection([('nothing', 'Nothing')], 'Carting'),
        'package_and_forwording': fields.float('Packing'),
        'loading_charges': fields.float('Loading Charges'),
        'inspection_charges': fields.float('Inspection Charges'),
        'delivery_charges': fields.float('Delivery Charges'),
        'rounding_shortage': fields.float('Rounding Shortage'),
        'vat_amount': fields.float('VAT Amount'),
        'additional_vat': fields.float('Additional Tax'),
        'debit_note_amount': fields.float('Debit Note Amount'),
        'advance_amount': fields.float('Advance Amount'),
        'retention_amount': fields.float('Retention Amount'),
        'net_amount': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Net Amount', track_visibility='always',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line', 'freight', 'package_and_forwording', 'insurance', 'loading_charges', 'inspection_charges', 'delivery_charges', 'other_charges', 'rounding_shortage', 'debit_note_amount', 'advance_amount', 'retention_amount'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'account_code': fields.many2one('account.account', 'Account Code'),
        'book_series_id': fields.many2one('product.order.series', 'Book Series'),
        'st_code':fields.selection([('nothing', 'Nothing')], 'S.T. Code'),
        'due_date': fields.date('Due Date'),
        'c_form':fields.boolean('C Form'),
        'state_id': fields.many2one('res.country.state', 'State'),
        'voucher_id': fields.many2one('account.voucher', 'Payment'),
        'tds_ac_code': fields.selection([('nothing', 'Nothing')], 'TDS A/C Code'),
        'tds_amount': fields.float('TDS Amount'),
        'other_ac_code': fields.selection([('nothing', 'Nothing')], 'Other Deduction A/C Code'),
        'other_amount': fields.float('Other Deduction Amount'),
        'maize_voucher_no':fields.char('Voucher No', size=16)
    }
    
    def get_voucher_number(self, cr, uid, invoice, debit_note, context):
        headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/json"}
        url = "%s:%s" % (invoice.company_id.account_ip, invoice.company_id.account_port)
        conn = httplib.HTTPConnection(url)
        voucher_no = invoice.maize_voucher_no
        
        if not invoice.maize_voucher_no:
            try:
                vounoSQL = "SELECT [VOUNO] FROM [MZFAS].[dbo].[FASPARM] where COCODE='1' and FINYEAR=%s and TYPE='DBK' and SUBTYPE='%s' and SERIES='%s'" % (invoice.move_id.period_id.fiscalyear_id.name, invoice.move_id.journal_id.code,  invoice.move_id.journal_id.series)
    
                conn.request("GET", "/cgi-bin/query", vounoSQL, headers)
                rsp = conn.getresponse()
                data_received = rsp.read()
                data = json.loads(data_received)
                voucher_no = int(data[0]['VOUNO'])
                
                vounoSQL = "UPDATE [MZFAS].[dbo].[FASPARM] SET [VOUNO]=%s where COCODE='1' and FINYEAR=%s and TYPE='DBK' and SUBTYPE='%s' and SERIES='%s'" % (voucher_no+1, invoice.move_id.period_id.fiscalyear_id.name, invoice.move_id.journal_id.code,  invoice.move_id.journal_id.series)
                conn.request("GET", "/cgi-bin/query", vounoSQL, headers)
                rsp = conn.getresponse()
                data_received = rsp.read()
                data = json.loads(data_received)
                
            except Exception, e:
                raise osv.except_osv(_('Error!'), _('Check your network connection as connection to maize accounting server %s failed !' % (url)))
            
        return voucher_no
    
    def create_debit_note(self, cr, uid, invoice, context):
        voucher_no = False
        
        
        return voucher_no
    
    def create_maize_voucher(self, cr, uid, invoice, context=None):
        headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/json"}
        url = "%s:%s" % (invoice.company_id.account_ip, invoice.company_id.account_port)
        conn = httplib.HTTPConnection(url)
        
        voucher_no = self.get_voucher_number(cr, uid, invoice, False, context)
        self.write(cr, uid, [invoice.id], {'maize_voucher_no':voucher_no})
        cr.commit()
        invoice = self.browse(cr, uid, invoice.id)
        
        debit_note_id = self.create_debit_note(cr, uid, invoice, context)
        
        maizeSQL = """INSERT INTO [MZFAS].[dbo].[PURTRAN] ([COCODE], [FINYEAR], [BKTYPE], [VOUNO], [VOUSRL], [SERIES], [RMQTY], [PAYDUE], [STCODE], 
                [TAXAMT], [GSTAMT], [STAMT], [SURAMT], [USERID], [ACTION], [PRTFLG], [ADVAMT], [DEDACCODE1], [DEDAMT1], [DEDACCODE2], [DEDAMT2], [RETAMT], 
                [DEBAMT], [DEBVOUNO], [DEBVATAMT], [RSNCODE], [STAMT1], [STAMT2], [DEBVATAMT1], [DEBVATAMT2], [EXCISE], [EXCISECESS], [EXCISEHCESS], [RATE], 
                [CFORMIND], [STATE], [REASON], [CONRETAMT], [DEDACCODE3], [DEBTAXABLEAMT], [AHDFLG], [DEDACCODE4], [DEDAMT4])
         VALUES
               ('%(COCODE)s',  '%(FINYEAR)s',  '%(BKTYPE)s',  '%(VOUNO)s',  '%(VOUSRL)s',  '%(SERIES)s',  '%(RMQTY)s',  '%(PAYDUE)s',  '%(STCODE)s',  '%(TAXAMT)s',  '%(GSTAMT)s',  '%(STAMT)s',  '%(SURAMT)s',  '%(USERID)s',  '%(ACTION)s',  
               '%(PRTFLG)s',  '%(ADVAMT)s',  '%(DEDACCODE1)s',  '%(DEDAMT1)s',  '%(DEDACCODE2)s',  '%(DEDAMT2)s',  '%(RETAMT)s',  '%(DEBAMT)s',  '%(DEBVOUNO)s',  '%(DEBVATAMT)s',  '%(RSNCODE)s',  '%(STAMT1)s',  '%(STAMT2)s',  '%(DEBVATAMT1)s',  
               '%(DEBVATAMT2)s',  '%(EXCISE)s',  '%(EXCISECESS)s',  '%(EXCISEHCESS)s',  '%(RATE)s',  '%(CFORMIND)s',  '%(STATE)s',  '%(REASON)s',  '%(CONRETAMT)s',  '%(DEDACCODE3)s',  '%(DEBTAXABLEAMT)s',  '%(AHDFLG)s',  '%(DEDACCODE4)s',  
               '%(DEDAMT4)s')"""
        maizeSQL = maizeSQL % {
            'COCODE': 1,  
            'FINYEAR': invoice.move_id.period_id.fiscalyear_id.name,
            'BKTYPE': invoice.move_id.journal_id.code,  
            'VOUNO': voucher_no,  
            'VOUSRL': 0,  
            'SERIES': invoice.move_id.journal_id.series,  
            'RMQTY': 0,  
            'PAYDUE': invoice.date_due,  
            'STCODE': 91,  
            'TAXAMT': invoice.amount_untaxed,  
            'GSTAMT': 0,  
            'STAMT': invoice.amount_tax + invoice.vat_amount,  
            'SURAMT': 0,  
            'USERID': invoice.user_id.user_code,
            'ACTION': invoice.id,      
            'PRTFLG': 'P',  
            'ADVAMT': invoice.advance_amount,  
            'DEDACCODE1': 0,  
            'DEDAMT1': 0,  
            'DEDACCODE2': 0,  
            'DEDAMT2': 0,  
            'RETAMT': 0,
            'DEBAMT': 0,
            'DEBVOUNO': debit_note_id,
            'DEBVATAMT': 0,
            'RSNCODE': 0,
            'STAMT1': 0,
            'STAMT2': 0,  
            'DEBVATAMT1': 0,  
            'DEBVATAMT2': 0,  
            'EXCISE': 0,  
            'EXCISECESS': 0,  
            'EXCISEHCESS': 0,  
            'RATE': 0,  
            'CFORMIND': invoice.c_form and 'Y' or 'F',
            'STATE': invoice.partner_id.state_id.name,  
            'REASON': '/',  
            'CONRETAMT': 0,  
            'DEDACCODE3': 0,  
            'DEBTAXABLEAMT': 0,  
            'AHDFLG': 0,  
            'DEDACCODE4': 0,    
            'DEDAMT4' : 0,
        }
        
        try:
            conn.request("GET", "/cgi-bin/query", maizeSQL, headers)
        except Exception, e:
            raise osv.except_osv(_('Error!'), _('Check your network connection as connection to maize accounting server %s failed !' % (url)))

        rsp = conn.getresponse()
        
        data_received = rsp.read()
        data = json.loads(data_received)

        count = 0
        for line in invoice.move_id.line_id:
            lineSQL = """INSERT INTO [MZFAS].[dbo].[TRANMAIN] (
                [COCODE], [FINYEAR], [BKTYPE], [BKSRS], [VOUNO], [VOUSRL], [VOUDATE], [VOUSTS], [FASCODE], [CRDBID], 
                [VOUAMT], [SUBCODE], [REFNO], [REFDAT], [REMK01], [REMK02], [REMK03], [REMK04], [USERID], [ACTION], [CVOUNO])
                VALUES (
                '%(COCODE)s', '%(FINYEAR)s', '%(BKTYPE)s', '%(BKSRS)s', '%(VOUNO)s', '%(VOUSRL)s', 
                '%(VOUDATE)s', '%(VOUSTS)s', '%(FASCODE)s', '%(CRDBID)s', '%(VOUAMT)s', '%(SUBCODE)s', 
                '%(REFNO)s', '%(REFDAT)s', '%(REMK01)s', '%(REMK02)s', '%(REMK03)s', '%(REMK04)s',
                '%(USERID)s', '%(ACTION)s', '%(CVOUNO)s')"""
            res = {
                'COCODE': 1, 
                'FINYEAR': invoice.move_id.period_id.fiscalyear_id.name, 
                'BKTYPE': invoice.move_id.journal_id.code, 
                'BKSRS': invoice.move_id.journal_id.series, 
                'VOUNO': voucher_no, 
                'VOUSRL': count, 
                'VOUDATE': line.date_created, 
                'VOUSTS': 'P', 
                'FASCODE': line.account_id.code, 
                'SUBCODE': '/', 
                'REFNO': invoice.move_id.id,
                'REFDAT': line.date, 
                'REMK01': line.name[0:35], 
                'REMK02': '/', 
                'REMK03': '/', 
                'REMK04': '/',
                'USERID': invoice.user_id.user_code, 
                'ACTION': invoice.id, 
                'CVOUNO': 0
            }
            
            if line.debit > 0:
                res.update({'CRDBID':'D', 'VOUAMT':line.debit})
            else:
                res.update({'CRDBID':'C', 'VOUAMT':line.credit})
            count += 1
            lineSQL = lineSQL % res
            
            conn.request("GET", "/cgi-bin/query", lineSQL, headers)
            rsp = conn.getresponse()
            
            data_received = rsp.read()
            data = json.loads(data_received)

        conn.close()
    
    def invoice_validate(self, cr, uid, ids, context=None):
        super(account_invoice, self).invoice_validate(cr, uid, ids, context)
        invoice = self.browse(cr, uid, ids)[0]
        self.create_maize_voucher(cr, uid, invoice, context)
        
        return True
    
    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'maize_voucher_no':0
        })
        return super(account_invoice, self).copy(cr, uid, id, default, context)

account_invoice()
