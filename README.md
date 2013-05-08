django-transaction-utils
========================

Utilities to make handling database transactions manually much easier.

About
-----

This code provides a decorator / context manager for transaction management in
Django on PostgreSQL. It is intended as a replacement for the existing Django
commit_on_success() function, and provides some nice features:
* Nested transactions: The top-level transaction will be a BEGIN/COMMIT/ROLLBACK
block; inner "transactions" are implemented as savepoints.
* Commits even if is_dirty is False, eliminating the mistake of forgetting to set
the dirty flag when doing database-modifying raw SQL.
* Better interaction with pgPool II, if you're using it.
* A workaround for a subtle but nasty bug in Django's transaction management.
For full details, check the README.md file.