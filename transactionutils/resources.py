try:
    from django.db import transaction

    from tastypie.resources import ModelResource

    class TransactionModelResource(ModelResource):
        """Wraps all write methods in a transaction"""
        def dispatch(self, request_type, request, **kwargs):
            if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
                with transaction.atomic:
                    return super(TransactionModelResource, self).dispatch(request_type, request, **kwargs)
            else:
                return super(TransactionModelResource, self).dispatch(request_type, request, **kwargs)
        
        # ModelResource does transaction management on this, but we are already handling that, so just skip it
        def patch_list(self, request, **kwargs):
            return super(ModelResource, self).patch_list(request, **kwargs)
except ImportError:
    pass
