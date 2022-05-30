# -*- coding: utf-8 -*-
from odoo import fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def __get_bank_statements_available_sources(self):
        rslt = super(AccountJournal, self).__get_bank_statements_available_sources()
        rslt.append(("mapped_csv", _("Mapped CSV File")))
        return rslt

    account_journal_bank_imports = fields.One2many('account.journal.bank.import', 'account_journal',
                                                   string='Import Line Columns')

    bank_account_source_line = fields.Integer(string='Line that holds the bank account')

    bank_account_source_col = fields.Integer(string='Column in line that holds the bank account',
                                             help='Leave blank if a single column')

    start_date_source_line = fields.Integer(
        string='Line that holds the start date',
        help='The start date is required to test that a file doe snot overlap with existing bank statements')

    start_date_source_column = fields.Integer(
        string='Column in line that holds the start date',
        help='Leave blank if a single column')

    start_date_date_format = fields.Selection(
        string='Format of Date',
        selection=[('%d/%m/%Y', 'dd/mm/yyyy'),
                   ('%d-%m-%Y', 'dd-mm-yyyy'),
                   ('%Y/%m/%d', 'yyyy/mm/dd'),
                   ('%Y-%m-%d', 'yyyy-mm-dd')],
        help='Technical field to manage same bank file with differing date formatted fields')

    first_trans_line = fields.Integer(
        string='First Transaction Line',
        help='e.g. If column header is first line then set this value to 2')



    def import_mapped_csv_statement(self):
        wizard = self.env['account.bank.statement.import.csv'].create({
            'bank_account': self.id
            })
        return {
            "name": "Import Bank Statement",
            "view_mode": "form",
            "res_model": wizard._name,
            "res_id": wizard.id,
            "type": "ir.actions.act_window",
            "nodestroy": False,
            "target": 'new',
        }


class AccountJournalBankImport(models.Model):
    _name = 'account.journal.bank.import'
    _description = 'Account Journal Bank Import'

    account_journal = fields.Many2one(comodel_name='account.journal', string='Journal', required=True)
    column_number = fields.Integer(string='Column Sequence')
    map_to = fields.Selection(string='Map To Column', selection=[
        ('date', 'Date'),
        ('reference', 'Reference'),
        ('amount', 'Amount'),
        ('particulars', 'Particulars'),
        ('code', 'Code'),
        ('other', 'Other Party'),
    ], help="Reference, Code, Particulars and Other Party should be linked to same named columns as used to "
            "identify payment orders that have been exported to the bank")

    ignore_if_value = fields.Char(string='Ignore Line if Value')
    date_format = fields.Selection(string='Format of Date',
                                   selection=[('%d/%m/%Y', 'dd/mm/yyyy'),
                                              ('%d-%m-%Y', 'dd-mm-yyyy'),
                                              ('%Y/%m/%d', 'yyyy/mm/dd'),
                                              ('%Y-%m-%d', 'yyyy-mm-dd')],
                                   help='Technical field to manage same bank file with differing date formatted fields')
