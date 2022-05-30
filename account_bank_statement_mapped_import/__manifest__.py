# -*- coding: utf-8 -*-
{
    "name": "Banking CSV Import",
    "version": "1.0",
    "summary": "Provide saved mapping for importing CSV bank statements",
    "description": """
This module allows for the configuration at a bank journal level to import a CSV file supplied
by the bank and to populate the bank statement lines.
    """,
    "category": "Accounting",
    "depends": [
        "account",
    ],
    "author": "Optimysme Limited",
    "data": [
        "views/account_journal.xml",
        "wizards/account_bank_statement_import.xml",
        "security/security.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
