# -*- coding: utf-8 -*-
import base64
import csv
import io
from datetime import datetime
import ast
import re

import dateutil.parser as dparser

from odoo import fields, models
from odoo.exceptions import UserError


class BankStatementImport(models.TransientModel):
    _name = "account.bank.statement.import.csv"
    _description = 'Bank Import CSV'

    ################################################################################
    # Fields
    ################################################################################
    bank_account = fields.Many2one(comodel_name='account.journal',
                                   string='Bank Account',
                                   domain="[('type','=','bank')]",
                                   required=True)

    import_file_name = fields.Binary(string='Import File', required=True,
        help='Get you bank statements in electronic format from your bank and select them here.')

    ignore_account = fields.Boolean(string='No Bank Account', help='Use to import credit card statements that have no bank account number')

    def check_bank_account(self, csv_lines):
        """
        values in set up are stored using actual numbers to avoid 0 = False issues
        so we subtract 1 for column and row values in this function
        """
        bank_account_source = self.bank_account.bank_account_source_line
        if not bank_account_source:
            raise UserError('The line for the bank account is not set up on the bank journal')
        bank_account_source_col = self.bank_account.bank_account_source_col
        bank_account_to_find = self.bank_account.bank_account_id
        if not bank_account_source_col:
            line_to_check = csv_lines[bank_account_source - 1]
            if isinstance(line_to_check, str):
                line_to_check = line_to_check.split(',')
            account_number = bank_account_to_find.acc_number
            for i in range(0, len(line_to_check)):
                found_bank = account_number.find(line_to_check[i])
                if found_bank == 0:
                    break
                if line_to_check[i].startswith('"'):
                    bank_to_check = line_to_check[i][1:-1]
                    found_bank = account_number.find(bank_to_check)
                    if found_bank == 0:
                        break

            if found_bank == -1:
                raise UserError('Bank Account not found')
        else:
            if isinstance(csv_lines[bank_account_source - 1], str):
                line_to_check = csv_lines[bank_account_source - 1].split(',')
            else:
                line_to_check = csv_lines[bank_account_source - 1]
            field_to_check = line_to_check[bank_account_source_col - 1]
            account_number = bank_account_to_find.acc_number
            found_bank = account_number.find(field_to_check)
            if found_bank == -1:
                raise UserError('Bank Account not found')

    def convert_string_to_date(self, date_string):
        # When saving to csv from Excel, sometimes it likes to add double quotes - just check and remove if any
        if date_string.startswith('"'):
            date_string = date_string[1:]

        if date_string.endswith('"'):
            date_string = date_string[:-1]

        date_format = self.bank_account.start_date_date_format
        if not date_format:
            raise UserError('No date format set for the header or row')
        date_value = datetime.strptime(date_string, date_format).date()
        return date_value

    def check_start_date(self, csv_lines):
        latest_bank_statement = self.env['account.bank.statement'].search([
            ('journal_id', '=', self.bank_account.id)
        ], order='date desc', limit=1)

        field_to_check = 'Not sure'
        error_message = """
                Date not able to be computed. Using value {value} from the first line in the file. 
                Check this line and make sure none of the values have a comma inside them as this throws out the import. 
                If yes, remove the comma and try again""".format(value=field_to_check)
        start_date = False

        if not latest_bank_statement:
            return False
        try:
            start_date_source_line = self.bank_account.start_date_source_line

            if not start_date_source_line:
                error_message = 'The line for the start date is not set up on the bank journal'
                raise Exception

            start_date_column = self.bank_account.start_date_source_column

            if not start_date_column:
                error_message = 'The column for the start date is not set up on the bank journal'
                raise Exception

            csv_line = csv_lines[start_date_source_line - 1].split(',')
            field_to_check = csv_line[start_date_column - 1]
            start_date = self.convert_string_to_date(field_to_check)

            if not start_date:
                raise Exception

            else:
                if latest_bank_statement.date > start_date:
                    error_message = 'This file has a start date < the latest bank statement for this account'
                    raise Exception

            return latest_bank_statement

        except Exception:
            if not start_date:
                error_message = """
                Start date not able to be computed. Using value {value} from the first line in the file. 
                Check this line and make sure none of the values have a comma inside them as this throws out the import. 
                If yes, remove the comma and try again""".format(value=field_to_check)
            raise UserError(error_message)

    def convert_to_float(self, value):
        new_value = False
        if isinstance(value, float):
            return value
        try:
            new_value = float(value)
        except:
            converted_value = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", value)
            if converted_value and converted_value[0]:
                new_value = float(converted_value[0])

        if new_value and not isinstance(new_value, float):
            raise UserError('cannot convert value of {val} from file to a float'.format(val=value))

        return new_value

    def map_csv_lines(self, csv_lines):
        # first rewrite CSV file into the mapped fields below based on the set up for the journal to simplify processing
        output_lines_map = {}
        columns_to_check = 20  # arbitrary number as the same column can be checked for ignore logic
        closing_date = False
        for i in range(0, len(csv_lines)):
            line = csv_lines[i].split(',')
            if not line or len(line) == 1: # ie empty line
                continue
            if i < self.bank_account.first_trans_line - 1:
                continue
            process_line = True

            # first check if should process line using ignore_if_value check
            for j in range(0, columns_to_check):
                import_recs = self.env['account.journal.bank.import'].search(
                    [('account_journal', '=', self.bank_account.id), ('column_number', '=', j)])
                for import_rec in import_recs:
                    if import_rec.ignore_if_value and import_rec.ignore_if_value == line[j]:
                        process_line = False

            if process_line:
                output_lines_map[i] = {}
                for j in range(0, columns_to_check):
                    import_recs = self.env['account.journal.bank.import'].search(
                        [('account_journal', '=', self.bank_account.id), ('column_number', '=', j)])
                    for import_rec in import_recs:
                        if import_rec.map_to == 'date':
                            try:
                                line_date = self.convert_string_to_date(line[j])
                            except:
                                raise UserError('Invalid date format found')
                            output_lines_map[i]['date'] = line_date
                            if not closing_date or line_date > closing_date:
                                closing_date = line_date
                        elif import_rec.map_to == 'amount':
                            output_lines_map[i]['amount'] = self.convert_to_float(line[j])
                        elif import_rec.map_to == 'reference':
                            output_lines_map[i]['reference'] = line[j]
                        elif import_rec.map_to == 'particulars':
                            output_lines_map[i]['particulars'] = line[j]
                        elif import_rec.map_to == 'code':
                            output_lines_map[i]['code'] = line[j]
                        elif import_rec.map_to == 'other':
                            output_lines_map[i]['other'] = line[j]

        return output_lines_map, closing_date

    def create_bank_statement(self, opening_balance, closing_balance, closing_date):
        bank_statement = self.env['account.bank.statement'].create({
            'date': closing_date,
            'balance_start': opening_balance,
            'balance_end_real': closing_balance,
            'journal_id': self.bank_account.id,
            'state': 'open'
        })
        return bank_statement

    def create_bank_statement_lines(self, bank_statement, output_lines_mapped):
        fields_to_map = []
        for k in output_lines_mapped:
            l = output_lines_mapped[k]
            if l.get('other', None):
                fields_to_map.append('other')
            if l.get('particulars', None):
                fields_to_map.append('particulars')
            if l.get('code', None):
                fields_to_map.append('code')
            if l.get('reference', None):
                fields_to_map.append('reference')
            break

        for k in output_lines_mapped:
            l = output_lines_mapped[k]

            payment_ref = ""
            for f in fields_to_map:
                if l.get(f):
                    payment_ref = append_non_null(payment_ref, l[f], " - ")

            self.env['account.bank.statement.line'].create(
                {
                    "statement_id": bank_statement.id,
                    "payment_ref": payment_ref,
                    "date": l["date"],
                    "amount": l["amount"]
                })

    def import_file(self):
        self.ensure_one()
        try:
            csv_true = base64.decodebytes(self.import_file_name).decode("utf-8")
        except:
            raise UserError('Only CSV file formats are supported')

        csv_lines = csv_true.replace("\r","").split("\n")
        if not self.ignore_account:
            self.check_bank_account(csv_lines)
        last_statement = self.check_start_date(csv_lines)
        if not last_statement:
            opening_balance = 0.0
        else:
            opening_balance = last_statement.balance_end_real

        output_lines_mapped, closing_date = self.map_csv_lines(csv_lines)

        if output_lines_mapped:
            movement = 0.0
            for k in output_lines_mapped:
                movement += float(output_lines_mapped[k]['amount'])
            closing_balance = opening_balance + movement
            bank_statement = self.create_bank_statement(opening_balance, closing_balance, closing_date)
            self.create_bank_statement_lines(bank_statement, output_lines_mapped)

        return


def append_non_null(original, str2, sep="\n"):
    """
    A local helper function, based on the version from jasperreports_viaduct.viaduct_helper
    """
    if not str2:
        return original
    str2 = str2.strip()
    if not str2:
        return original
    if not original:
        return str2
    return original + sep + str2
