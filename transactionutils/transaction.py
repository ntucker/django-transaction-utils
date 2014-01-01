from functools import wraps

import psycopg2.extensions

from django.db import transaction, DEFAULT_DB_ALIAS, connections

class _Transaction(object):

    """ This class manages a particular transaction or savepoint block, using context
manager-style __enter__ and __exit__ statements. We don't use it directly
(for reasons noted below), but as a delegate for the _TransactionWrapper
class.
"""
    
    def __init__(self, using):
        self.using = using
        self.sid = None
    
    def __enter__(self):
        if transaction.is_managed(self.using):
            # We're already in a transaction; create a savepoint.
            self.sid = transaction.savepoint(self.using)
        else:
            transaction.enter_transaction_management(using=self.using)
            transaction.managed(True, using=self.using)
   
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value is None:
            # commit operation
            if self.sid is None:
                # Outer transaction
                try:
                    transaction.commit(self.using)
                except:
                    transaction.rollback(self.using)
                    raise
                finally:
                    self._leave_transaction_management()
            else:
                # Inner savepoint
                try:
                    transaction.savepoint_commit(self.sid, self.using)
                except:
                    transaction.savepoint_rollback(self.sid, self.using)
                    raise
        else:
            # rollback operation
            if self.sid is None:
                # Outer transaction
                transaction.rollback(self.using)
                self._leave_transaction_management()
            else:
                # Inner savepoint
                transaction.savepoint_rollback(self.sid, self.using)
        
        return False
            # Returning False here means we did not gobble up the exception, so the
            # exception process should continue.
    
    def _leave_transaction_management(self):
        transaction.leave_transaction_management(using=self.using)
        if not connections[self.using].is_managed() and connections[self.using].features.uses_autocommit:
            connections[self.using]._set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            # Patch for bug in Django's psycopg2 backend; see:
            # https://code.djangoproject.com/ticket/16047
    

class _TransactionWrapper:

    """ This class wraps the above _Transaction class. We do this to allow reentrancy
and thread-safety. When being used as a decorator, only one _TransactionWrapper
object is created per function being wrapped, and thus we can't store the state
of the tranasction here (because multiple concurrent calls in the same address
space to the same function would cause the state to be crunched), so delegate
that to a _Transaction object that is created at the appropriate time.
The "appropriate time" is two places: If the _TransactionWrapper is being used
as a context manager, it's when the __enter__ function is called; if it is being
used as a decorator, it's when the decorated function is about to be called
(see the `inner` function below in __call__).
The __enter__ and __exit__ functions on _TransactionWrapper are only called
if we're using xact() as a context manager; if we're using it as a decorator,
they're skipped and self.transaction is always None. Similarly, __call__ is
not used if this is a context manager usage. This is not super-elegant, but
it's the only way I've found to allow xact() to be used as both a context
manager and a decorator using the same syntax.
"""
    
    def __init__(self, using):
        self.using = using
        self.transaction = None
    
    def __enter__(self):
        if self.transaction is None:
            self.transaction = _Transaction(self.using)
        return self.transaction.__enter__()
        
    def __exit__(self, exc_type, exc_value, traceback):
        return self.transaction.__exit__(exc_type, exc_value, traceback)

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            with _Transaction(self.using):
                return func(*args, **kwargs)
        return inner


def xact(using=None):
    if using is None:
        using = DEFAULT_DB_ALIAS
    if callable(using):
        # We end up here if xact is being used as a completely bare decorator:
        # @xact
        # (not even an empty parameter list)
        return _TransactionWrapper(DEFAULT_DB_ALIAS)(using)
            # Note that `using` here is *not* the database alias; it's the actual function
            # being decorated.
    else:
        # We end up here if xact is being used as a parameterized decorator (including
        # default parameter):
        # @xact(db)
        # or @xact()
        # ... or as a context manager:
        # with xact():
        # ...
        return _TransactionWrapper(using)

# Addition by ntucker for class based views
def XactModelFormViewMetaFactory(using=None):
    class XactModelFormViewMeta(type):
        def __new__(cls, name, bases, attrs):
            cls = type.__new__(cls, name, bases, attrs)
            cls.form_valid = transaction.atomic(using)(cls.form_valid)
            return cls
    return XactModelFormViewMeta
