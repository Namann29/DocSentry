# Importing the modules registers the parsers.
from . import bank_statement, identity, invoice, letters, salary_slip  # noqa: F401
from .base import FieldDTO, ParseResult, get_parser  # noqa: F401